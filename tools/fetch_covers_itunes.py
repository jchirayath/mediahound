#!/usr/bin/env python3
"""Fill missing album covers from the iTunes Search API (free, no key, high-res art).

Runs after the MusicBrainz pass: for every music item still lacking a cover it queries
iTunes and accepts a result ONLY if it validates against the album/artist (token overlap),
so a vague "Various Artists / Hits" can't grab a random soundtrack. Matched art is stored
as a 600×600 artwork URL. Resumable (skips items that already have a poster); saves every
BATCH items. Items it can't confidently match are written to a residual CSV for a Claude
title-cleanup pass.

Usage:
    fetch_covers_itunes.py /path/to/Library/config.toml [LIMIT]
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
from mediahound import pipeline

BATCH = 25
_STOP = {"the", "a", "an", "and", "of", "to", "feat", "featuring", "vol", "volume",
         "remaster", "remastered", "edition", "deluxe", "expanded", "disc", "cd", "ep", "single"}
_VARIOUS = re.compile(r"various|soundtrack|ost|original (motion|cast)|compilation|^v\.?a\.?$", re.I)


def toks(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t and t not in _STOP}


def best_match(title: str, artist: str, results: list) -> dict | None:
    """Pick the iTunes result that genuinely matches — or None. Conservative on purpose:
    a missing cover is better than a wrong one."""
    qt, qa = toks(title), toks(artist)
    if not qt:
        return None
    is_va = bool(_VARIOUS.search(artist or "")) or not qa
    if is_va and len(qt) < 2:
        return None                       # "Hits" / "Live" etc. are too generic to trust
    best, best_score = None, 0.0
    for r in results:
        ra, rart = toks(r.get("collectionName", "")), toks(r.get("artistName", ""))
        if not ra:
            continue
        title_overlap = len(qt & ra) / len(qt)
        artist_ok = is_va or bool(qa & rart) or title_overlap >= 0.85
        thresh = 0.7 if is_va else 0.5
        if title_overlap >= thresh and artist_ok and title_overlap > best_score:
            best, best_score = r, title_overlap
    return best


def itunes_lookup(title: str, artist: str) -> dict | None:
    # For a Various-Artists/soundtrack comp, search by the album title alone (the artist
    # field is noise); otherwise include the artist to disambiguate.
    is_va = bool(_VARIOUS.search(artist or "")) or not artist
    term = title if is_va else f"{artist} {title}"
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": term, "entity": "album", "limit": 5})
    with urllib.request.urlopen(url, timeout=12) as r:
        results = json.load(r).get("results", [])
    return best_match(title, artist, results)


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
    print(f"iTunes cover pass over {len(todo)} item(s) lacking art…", flush=True)

    hits = 0
    residual = []
    for i, m in enumerate(todo, 1):
        try:
            r = itunes_lookup(m.get("title", ""), m.get("artist", ""))
        except Exception:
            r = None
        if r and r.get("artworkUrl100"):
            cover = r["artworkUrl100"].replace("100x100bb", "600x600bb")
            m["poster"], m["images"] = cover, [cover]
            m["source"] = {"name": "iTunes", "url": r.get("collectionViewUrl", "")}
            hits += 1
        else:
            residual.append(["music", m.get("title", ""), m.get("artist", ""), m.get("year", "")])
        if i % BATCH == 0:
            store.save()
            print(f"  …{i}/{len(todo)} | {hits} covered", flush=True)
        time.sleep(0.25)                  # be polite to the API

    store.save()
    pipeline._write_site(cfg, store)
    res_path = cfg.data_dir.parent / "covers-residual.csv"
    with res_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["media_type", "title", "artist", "year"]); w.writerows(residual)
    print(f"Done. {hits}/{len(todo)} covered via iTunes. {len(residual)} unmatched → {res_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
