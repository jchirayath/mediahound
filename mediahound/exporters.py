"""Export the catalog to other services / formats — move your data freely.

- **Letterboxd** (movies): the CSV schema their importer accepts (Title, Year, Rating10,
  WatchedDate, Tags), driven by your personal ratings/tags/seen state.
- **Generic JSON**: the catalog is already `data/collection.json`; this writes a clean,
  documented copy so it's a first-class, stable export too.

Personal data (ratings, tags) lives in `data/corrections.json` (admin-only), so exporters read
it from the Store rather than from the published catalog, which has those fields stripped.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


def _personal(store) -> dict:
    """id → correction dict (holds my_rating / tags / my_note)."""
    return getattr(store, "corrections", {}) or {}


def export_letterboxd(store, out_path: Path) -> int:
    """Write a Letterboxd-import CSV of the **movies**. Returns the row count.

    Columns per Letterboxd's import spec: Title, Year, Rating10 (your 1–10 rating),
    WatchedDate (the date you marked it seen), Tags (your shelves)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    corr = _personal(store)
    rows = 0
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Title", "Year", "Rating10", "WatchedDate", "Tags"])
        for m in store.collection:
            if (m.get("media_type") or "movie") != "movie":
                continue
            c = corr.get(m.get("id"), {})
            rating = c.get("my_rating")
            tags = c.get("tags") or []
            watched = m.get("date_seen") if m.get("seen") else ""
            w.writerow([m.get("title") or "", m.get("year") or "",
                        rating if rating is not None else "",
                        watched or "", ", ".join(tags)])
            rows += 1
    return rows


def export_json(store, out_path: Path) -> int:
    """Write the whole catalog as JSON (the stable, documented generic export)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(store.collection, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(store.collection)
