#!/usr/bin/env python3
"""Layer B — resumable online enrichment of a MediaHound music library.

Walks every music item missing cover art and fills cover + any blank
year/genre/label/tracklist from the configured provider (MusicBrainz, ~1 req/s).

Resumable: an item that already has a `poster` is skipped, so re-running after an
interruption picks up where it left off. Saves to disk every BATCH items.

Usage:
    enrich_music_library.py /path/to/Library/config.toml [LIMIT]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mediahound.config import load_config
from mediahound.store import Store
from mediahound.csvio import _enrich
from mediahound import pipeline

BATCH = 25


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cfg = load_config(Path(sys.argv[1]).resolve())
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

    store = Store(cfg.data_dir)
    todo = [m for m in store.collection
            if m.get("media_type") == "music" and not m.get("poster")]
    if limit:
        todo = todo[:limit]
    total = len(todo)
    print(f"Enriching {total} music item(s) lacking cover art "
          f"(~1 req/s → ~{total // 60 + 1} min)…", flush=True)

    hits = misses = 0
    for i, item in enumerate(todo, 1):
        # _enrich mutates the dict in place; it's the same object held by the store.
        if _enrich(cfg, item, log=lambda *_: None):
            hits += 1
        else:
            misses += 1
        if i % BATCH == 0:
            store.save()
            print(f"  …{i}/{total} | {hits} matched, {misses} no-match", flush=True)

    store.save()
    pipeline._write_site(cfg, store)
    print(f"Done. {hits}/{total} enriched (cover/fields), {misses} no match. "
          f"Site rebuilt at {cfg.data_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
