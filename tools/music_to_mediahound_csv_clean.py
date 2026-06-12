#!/usr/bin/env python3
"""Walk a music library and emit a CLEAN MediaHound-importable CSV — one row per album.

Layer-A cleanup over the original `music_to_mediahound_csv.py`:
  1. Title cleanup keeps brackets balanced (fixes "...(2 Of 2" truncation).
  2. Global artist canonicalization — one display spelling per artist across the
     whole catalog (ABBA/Abba, AC/DC/AC-DC, creed/Creed → one canonical form).
  3. Genre normalization — raw ID3 strings mapped to a small controlled vocab;
     bare "Other"/"Unknown" dropped.
  4. Audiobook / spoken-word detection — routed OUT of the music CSV into a
     review file instead of polluting the catalog.
  5. Placeholder albums ("[non-album tracks]", "Unknown") collapsed to per-artist
     "Singles" and flagged.

Outputs (next to the library, originals preserved):
    mediahound-music.clean.csv    — import this
    mediahound-music.review.csv   — audiobooks + single-track / suspicious rows to eyeball

Usage:
    music_to_mediahound_csv_clean.py [LIBRARY_DIR] [CLEAN_OUT]
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from mutagen import File as MutaFile

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Volumes/Multimedia/Music")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "mediahound-music.clean.csv"
REVIEW = OUT.with_name("mediahound-music.review.csv")
AUDIO = {".mp3", ".flac", ".m4a", ".m4p", ".aac", ".wma", ".ogg", ".oga", ".wav", ".aiff", ".aif", ".alac"}

_YEAR = re.compile(r"(19|20)\d{2}")
# Trailing disc/cd marker only: "(Disc 1)", "[CD 2]", "Disk 3" at end of string.
_DISC = re.compile(r"\s*[\(\[]?\s*(?:disc|cd|disk)\s*\d+[^\)\]]*[\)\]]?\s*$", re.I)
_PLACEHOLDER_ALBUM = re.compile(r"^\s*(\[non-?album.*\]|unknown.*|various|untitled|\(null\)|\(?singles?\)?)\s*$", re.I)

# --- audiobook / spoken-word signals -------------------------------------------------
_SPOKEN_GENRE = re.compile(r"audiobook|audio book|spoken|speech|podcast|radio drama|comedy radio", re.I)
_TRACKY = re.compile(r"^\s*(track|disc|chapter|part|side)\s*\d+\s*$", re.I)
_ABOOK_TITLE = re.compile(r"unabridged|abridged|audiobook|read by|\bbbc (radio|audio)\b", re.I)

# --- genre normalization -------------------------------------------------------------
# canonical bucket -> list of substrings that map to it (checked in order)
_GENRE_MAP: list[tuple[str, tuple[str, ...]]] = [
    ("Soundtrack",   ("soundtrack", "score", "ost", "musical")),
    ("Hip-Hop",      ("hip-hop", "hip hop", "hiphop", "rap")),
    ("R&B",          ("r&b", "rnb", "r and b", "rhythm and blues", "soul", "motown", "funk")),
    ("Electronic",   ("electronic", "electronica", "techno", "house", "trance", "dance", "edm", "ambient", "downtempo", "drum & bass", "dnb", "idm")),
    ("Metal",        ("metal", "thrash", "death metal", "black metal")),
    ("Punk",         ("punk", "hardcore", "emo")),
    ("Alternative",  ("alternative", "alt-rock", "alt rock", "indie", "grunge", "new wave")),
    ("Classical",    ("classical", "baroque", "opera", "orchestral", "symphony", "chamber")),
    ("Jazz",         ("jazz", "bebop", "swing", "big band")),
    ("Blues",        ("blues",)),
    ("Country",      ("country", "bluegrass", "americana", "western")),
    ("Folk",         ("folk", "singer-songwriter", "singer/songwriter")),
    ("Reggae",       ("reggae", "ska", "dub", "dancehall")),
    ("Latin",        ("latin", "salsa", "bossa", "samba", "tango", "flamenco")),
    ("World",        ("world", "celtic", "african", "indian", "traditional")),
    ("Comedy",       ("comedy", "humour", "humor", "parody", "novelty")),
    ("Gospel",       ("gospel", "christian", "worship", "religious")),
    ("Holiday",      ("christmas", "holiday")),
    ("Pop",          ("pop", "vocal", "easy listening", "adult contemporary")),
    ("Rock",         ("rock", "classic rock",)),
]
_GENRE_DROP = {"other", "unknown", "misc", "miscellaneous", "general", "none", "", "audio", "music"}


def first(v):
    if v is None:
        return None
    if isinstance(v, list):
        v = v[0] if v else None
    s = str(v).strip() if v is not None else None
    return s or None


def read_tags(p: Path) -> dict | None:
    try:
        f = MutaFile(str(p), easy=True)
    except Exception:
        return None
    if f is None or f.tags is None:
        return None
    t = f.tags
    return {
        "album": first(t.get("album")),
        "artist": first(t.get("artist")),
        "albumartist": first(t.get("albumartist")) or first(t.get("album artist")),
        "date": first(t.get("date")) or first(t.get("originaldate")) or first(t.get("year")),
        "genre": first(t.get("genre")),
        "track": first(t.get("tracknumber")),
        "disc": first(t.get("discnumber")),
        "title": first(t.get("title")),
    }


def balance_brackets(s: str) -> str:
    """Drop a dangling unmatched leading/trailing bracket left by disc-stripping,
    without eating brackets that are balanced (the old `.strip('()[]')` bug)."""
    s = s.strip(" -\t")
    # trailing unmatched closer
    while s and s[-1] in ")]" and s.count("(" if s[-1] == ")" else "[") < s.count(s[-1]):
        s = s[:-1].strip(" -")
    # leading unmatched opener
    while s and s[0] in "([" and s.count(")" if s[0] == "(" else "]") < s.count(s[0]):
        s = s[1:].strip(" -")
    return s.strip(" -")


def clean_album(album: str) -> str:
    a = _DISC.sub("", album)
    a = balance_brackets(a)
    return a or album.strip()


def parse_folder(album_dir: Path) -> dict:
    name = album_dir.name
    m = re.match(r"^(.*?)\s*-\s*((?:19|20)\d{2})\s*-\s*(.*)$", name)
    if m:
        artist, year, album = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
    else:
        ym = _YEAR.search(name)
        year = int(ym.group(0)) if ym else None
        album = _YEAR.sub("", name).strip(" -")
        artist = album_dir.parent.name if album_dir.parent != ROOT else None
    return {"artist": artist, "year": year, "album": clean_album(album) or name}


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def year_of(date: str | None) -> int | None:
    if not date:
        return None
    m = _YEAR.search(date)
    return int(m.group(0)) if m else None


def track_key(rec):
    def num(s):
        if not s:
            return 0
        m = re.match(r"\d+", str(s))
        return int(m.group(0)) if m else 0
    return (num(rec.get("disc")), num(rec.get("track")), rec.get("title") or "")


def norm_genres(raw: list[str]) -> list[str]:
    """Map a list of raw ID3 genre strings to <=2 canonical buckets."""
    out: list[str] = []
    for g in raw:
        for piece in re.split(r"[;/,|]", g or ""):
            p = piece.strip().lower()
            if not p or p in _GENRE_DROP or _SPOKEN_GENRE.search(p):
                continue
            bucket = None
            for canon, subs in _GENRE_MAP:
                if any(sub in p for sub in subs):
                    bucket = canon
                    break
            bucket = bucket or piece.strip().title()
            if bucket not in out:
                out.append(bucket)
    return out[:2]


def canonical_artists(albums: dict) -> dict[str, str]:
    """One display spelling per artist across the whole catalog.
    Pick by: total frequency, then more punctuation preserved (AC/DC > ACDC),
    then proper mixed-case, then longer."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for recs in albums.values():
        for r in recs:
            a = r["_artist"]
            if a:
                counts[norm_key(a)][a] += 1
    chosen: dict[str, str] = {}
    for k, c in counts.items():
        def score(item):
            name, n = item
            punct = len(re.findall(r"[^\w\s]", name))
            mixed = 1 if (name != name.lower() and name != name.upper()) else 0
            return (n, punct, mixed, len(name))
        chosen[k] = max(c.items(), key=score)[0]
    return chosen


def is_audiobook(album: str, genre_raw: list[str], titles: list[str], genres: list[str]) -> bool:
    if _ABOOK_TITLE.search(album or ""):
        return True
    # Spoken-word is an audiobook signal only when it DOMINATES — a music album with a
    # couple of bonus interview tracks tagged "Books & Spoken" (e.g. Thriller) is not one.
    spoken = sum(1 for g in genre_raw if _SPOKEN_GENRE.search(g or ""))
    if genre_raw and spoken >= len(genre_raw) * 0.5:
        return True
    # "Track NN"-style titles only signal an audiobook when there's NO music genre
    # to anchor the album — otherwise it's just a poorly-tagged music rip.
    if titles and not genres:
        tracky = sum(1 for t in titles if _TRACKY.match(t))
        if tracky >= max(3, len(titles) * 0.7):
            return True
    return False


def main() -> int:
    if not ROOT.is_dir():
        print(f"Not a directory: {ROOT}", file=sys.stderr)
        return 2
    print(f"Scanning {ROOT} …", flush=True)
    albums: dict[tuple, list] = defaultdict(list)
    scanned = 0
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in AUDIO:
            continue
        scanned += 1
        if scanned % 1000 == 0:
            print(f"  …{scanned} audio files, {len(albums)} albums so far", flush=True)
        tags = read_tags(p) or {}
        album = tags.get("album")
        artist = tags.get("albumartist") or tags.get("artist")
        year = year_of(tags.get("date"))
        if not album or not artist:
            fb = parse_folder(p.parent)
            album = album or fb["album"]
            artist = artist or fb["artist"] or "Unknown Artist"
            year = year or fb["year"]
        # A placeholder album tag ("(Single)", "[non-album tracks]", "Unknown") carries no
        # real album name — recover it from the folder ("Coldplay - 2003 - Clocks" → Clocks);
        # only fall back to a per-artist "Singles" bucket when the folder doesn't help either.
        placeholder = bool(_PLACEHOLDER_ALBUM.match(album or ""))
        if placeholder:
            fb_album = parse_folder(p.parent)["album"]
            if fb_album and not _PLACEHOLDER_ALBUM.match(fb_album):
                album, placeholder = fb_album, False
        album_clean = "Singles" if placeholder else (clean_album(album) or album)
        key = (norm_key(artist), norm_key(album_clean))
        albums[key].append({**tags, "_album": album_clean, "_artist": artist,
                            "_year": year, "_placeholder": placeholder})

    print(f"Scanned {scanned} audio files → {len(albums)} albums. Canonicalizing …", flush=True)
    canon = canonical_artists(albums)

    clean_rows, review_rows = [], []
    for (_, _), recs in sorted(albums.items(),
                               key=lambda kv: (kv[1][0]["_artist"].lower(), kv[1][0]["_album"].lower())):
        title = Counter(r["_album"] for r in recs).most_common(1)[0][0]
        raw_artist = Counter(r["_artist"] for r in recs).most_common(1)[0][0]
        artist = canon.get(norm_key(raw_artist), raw_artist)
        years = [r["_year"] for r in recs if r.get("_year")]
        year = Counter(years).most_common(1)[0][0] if years else ""
        genre_raw = [r["genre"] for r in recs if r.get("genre")]
        genres = norm_genres(genre_raw)
        tracks = [r["title"] for r in sorted(recs, key=track_key) if r.get("title")]
        seen, tl = set(), []
        for t in tracks:
            if t.lower() not in seen:
                seen.add(t.lower())
                tl.append(t)
        row = ["music", title, artist, year, "CD", "; ".join(genres), "; ".join(tl[:80])]

        if is_audiobook(title, genre_raw, tl, genres):
            review_rows.append(["audiobook", *row[1:]])
        elif any(r.get("_placeholder") for r in recs):
            review_rows.append(["singles", *row[1:]])
        elif len(tl) <= 1 and not years:
            # one track + no year: likely a stray single, not a real album
            review_rows.append(["single-track", *row[1:]])
        else:
            clean_rows.append(row)

    header = ["media_type", "title", "artist", "year", "format", "genres", "tracklist"]
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(clean_rows)
    with REVIEW.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["flag", *header[1:]])
        w.writerows(review_rows)

    print(f"Done. {len(clean_rows)} clean album rows → {OUT}", flush=True)
    print(f"      {len(review_rows)} flagged rows → {REVIEW}", flush=True)
    flags = Counter(r[0] for r in review_rows)
    print("      review breakdown:", dict(flags))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
