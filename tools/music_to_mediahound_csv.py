#!/usr/bin/env python3
"""Walk a music library and emit a MediaHound-importable CSV — one row per album.

Reads ID3/Vorbis/MP4 tags (album, album-artist, year, genre, track, title) via mutagen and groups
files into albums. Files with no usable tags fall back to parsing the folder name
("Artist - YYYY - Album"). Output columns match MediaHound's music CSV importer:
    media_type,title,artist,year,format,genres,tracklist
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from mutagen import File as MutaFile

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Volumes/Multimedia/Music")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "mediahound-music.csv"
AUDIO = {".mp3", ".flac", ".m4a", ".m4p", ".aac", ".wma", ".ogg", ".oga", ".wav", ".aiff", ".aif", ".alac"}

_YEAR = re.compile(r"(19|20)\d{2}")
_DISC = re.compile(r"\s*[\(\[]?\s*(disc|cd|disk)\s*\d+.*$", re.I)
_NOISE_DIR = re.compile(r"\s*[\(\[].*?(remaster|deluxe|expanded|bonus|edition|reissue|mono|stereo).*?[\)\]]", re.I)


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


def parse_folder(album_dir: Path) -> dict:
    """Best-effort artist/year/album from a folder named like 'Artist - YYYY - Album [tag]'.
    Falls back to parent=artist for 'Artist/Album' layouts."""
    name = album_dir.name
    m = re.match(r"^(.*?)\s*-\s*((?:19|20)\d{2})\s*-\s*(.*)$", name)
    if m:
        artist, year, album = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
    else:
        ym = _YEAR.search(name)
        year = int(ym.group(0)) if ym else None
        album = _DISC.sub("", name)
        album = _YEAR.sub("", album).strip(" -()[]")
        # 'Artist/Album' layout: the grandparent is likely the artist
        artist = album_dir.parent.name if album_dir.parent != ROOT else None
    album = _DISC.sub("", album).strip(" -()[]") or name
    return {"artist": artist, "year": year, "album": album}


def norm_key(s: str) -> str:
    """Collapse case/punctuation so 'AC/DC' and 'AC-DC' (tags vs folder names) group together."""
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
        album_clean = _DISC.sub("", album).strip(" -()[]") or album
        key = (norm_key(artist), norm_key(album_clean))
        albums[key].append({**tags, "_album": album_clean, "_artist": artist, "_year": year})

    print(f"Scanned {scanned} audio files → {len(albums)} albums. Writing {OUT} …", flush=True)
    rows = 0
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["media_type", "title", "artist", "year", "format", "genres", "tracklist"])
        for (_, _), recs in sorted(albums.items(), key=lambda kv: (kv[1][0]["_artist"].lower(), kv[1][0]["_album"].lower())):
            title = Counter(r["_album"] for r in recs).most_common(1)[0][0]
            artist = Counter(r["_artist"] for r in recs).most_common(1)[0][0]
            years = [r["_year"] for r in recs if r.get("_year")]
            year = Counter(years).most_common(1)[0][0] if years else ""
            genres = [r["genre"] for r in recs if r.get("genre")]
            genre = "; ".join(dict.fromkeys(g for g, _ in Counter(genres).most_common(3))) if genres else ""
            tracks = [r["title"] for r in sorted(recs, key=track_key) if r.get("title")]
            seen, tl = set(), []
            for t in tracks:
                if t.lower() not in seen:
                    seen.add(t.lower())
                    tl.append(t)
            w.writerow(["music", title, artist, year, "CD", genre, "; ".join(tl[:80])])
            rows += 1
    print(f"Done. Wrote {rows} album rows → {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
