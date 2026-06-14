#!/usr/bin/env python3
"""Fill missing album covers from free music databases (iTunes + Deezer — no API key).

Runs after the MusicBrainz pass. For every music item still lacking a cover it queries each
provider in turn and accepts a result ONLY if it validates against the album/artist (token
overlap), so a vague "Various Artists / Hits" can't grab a random soundtrack. The first
validated hit wins; art is stored as a ~600px URL. Resumable (skips items that already have a
poster); saves every BATCH items. Items it can't confidently match are written to a residual
CSV — many are bootlegs / personal compilations with no commercial cover anywhere, which keep
the app's generated placeholder rather than a wrong image.

Usage:
    fetch_covers.py /path/to/Library/config.toml [LIMIT]
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mediahound.config import load_config
from mediahound.store import Store
from mediahound import pipeline, keystore

_DISCOGS_TOKEN = keystore.get_key("DISCOGS_TOKEN")   # read once (avoids repeated keychain access)

BATCH = 25
_STOP = {"the", "a", "an", "and", "of", "to", "feat", "featuring", "vol", "volume",
         "remaster", "remastered", "edition", "deluxe", "expanded", "disc", "cd", "ep", "single"}
_VARIOUS = re.compile(r"various|soundtrack|ost|original (motion|cast)|compilation|^v\.?a\.?$", re.I)


def toks(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t and t not in _STOP}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "MediaHound/0.7 cover-fetch"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.load(r)


def _candidates_itunes(term: str) -> list[dict]:
    data = _get("https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": term, "entity": "album", "limit": 5}))
    out = []
    for r in data.get("results", []):
        art = r.get("artworkUrl100", "")
        if art:
            out.append({"album": r.get("collectionName", ""), "artist": r.get("artistName", ""),
                        "cover": art.replace("100x100bb", "600x600bb"),
                        "source": "iTunes", "url": r.get("collectionViewUrl", "")})
    return out


def _candidates_deezer(term: str) -> list[dict]:
    data = _get("https://api.deezer.com/search/album?" + urllib.parse.urlencode({"q": term, "limit": 5}))
    out = []
    for r in data.get("data", []):
        cover = r.get("cover_xl") or r.get("cover_big") or r.get("cover_medium")
        if cover:
            out.append({"album": r.get("title", ""), "artist": (r.get("artist") or {}).get("name", ""),
                        "cover": cover, "source": "Deezer", "url": r.get("link", "")})
    return out


def _candidates_discogs(term: str) -> list[dict]:
    if not _DISCOGS_TOKEN:
        return []
    data = _get("https://api.discogs.com/database/search?" + urllib.parse.urlencode(
        {"q": term, "type": "release", "per_page": 5, "token": _DISCOGS_TOKEN}))
    out = []
    for r in data.get("results", []):
        cover = r.get("cover_image") or r.get("thumb")
        if not cover or "spacer.gif" in cover:        # Discogs' "no art" placeholder
            continue
        title = r.get("title", "")
        artist, album = title.split(" - ", 1) if " - " in title else ("", title)
        out.append({"album": album, "artist": artist, "cover": cover,
                    "source": "Discogs", "url": "https://www.discogs.com" + (r.get("uri", "") or "")})
    time.sleep(0.9)                                   # stay under Discogs' 60/min authenticated limit
    return out


# iTunes/Deezer first (fast, no key); Discogs last — deepest catalogue for obscure releases.
PROVIDERS = [_candidates_itunes, _candidates_deezer, _candidates_discogs]


def best_cover(title: str, artist: str) -> dict | None:
    """First validated cover across providers — conservative, since a missing cover beats a wrong one."""
    qt, qa = toks(title), toks(artist)
    if not qt:
        return None
    is_va = bool(_VARIOUS.search(artist or "")) or not qa
    if is_va and len(qt) < 2:
        return None                       # "Hits" / "Live" etc. — too generic to trust
    term = title if is_va else f"{artist} {title}"
    for provider in PROVIDERS:
        try:
            results = provider(term)
        except Exception:
            results = []
        best, best_score = None, 0.0
        for r in results:
            ra, rart = toks(r["album"]), toks(r["artist"])
            if not ra:
                continue
            overlap = len(qt & ra) / len(qt)
            artist_ok = is_va or bool(qa & rart) or overlap >= 0.85
            if overlap >= (0.7 if is_va else 0.5) and artist_ok and overlap > best_score:
                best, best_score = r, overlap
        if best:
            return best
        time.sleep(0.2)
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cfg = load_config(Path(sys.argv[1]).resolve())
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    store = Store(cfg.data_dir)
    todo = [m for m in store.collection if m.get("media_type") == "music" and not m.get("poster")]
    if limit:
        todo = todo[:limit]
    print(f"Cover pass (iTunes -> Deezer) over {len(todo)} item(s) lacking art...", flush=True)

    hits = 0
    by_src: dict[str, int] = {}
    residual = []
    for i, m in enumerate(todo, 1):
        r = best_cover(m.get("title", ""), m.get("artist", ""))
        if r:
            m["poster"], m["images"] = r["cover"], [r["cover"]]
            m["source"] = {"name": r["source"], "url": r["url"]}
            hits += 1
            by_src[r["source"]] = by_src.get(r["source"], 0) + 1
        else:
            residual.append(["music", m.get("title", ""), m.get("artist", ""), m.get("year", "")])
        if i % BATCH == 0:
            store.save()
            print(f"  ...{i}/{len(todo)} | {hits} covered {by_src}", flush=True)
        time.sleep(0.2)

    store.save()
    pipeline._write_site(cfg, store)
    res_path = cfg.data_dir.parent / "covers-residual.csv"
    with res_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["media_type", "title", "artist", "year"]); w.writerows(residual)
    print(f"Done. {hits}/{len(todo)} newly covered {by_src}. {len(residual)} still unmatched -> {res_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
