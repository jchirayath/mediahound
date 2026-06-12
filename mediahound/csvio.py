"""Bulk add/export catalog items via CSV — no photos required.

`mediahound import catalog.csv` turns each row into a catalog item (movie or music) and,
with --online, enriches it via the metadata providers (cover art + missing fields).
`mediahound export -o catalog.csv` writes the whole catalog back out for backup/migration.
"""
from __future__ import annotations

import csv
import re
from datetime import UTC, datetime
from pathlib import Path

from .links import hear_links, listen_links, play_links, read_links
from .resale import estimate

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-") or "item"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _split(s: str | None) -> list[str]:
    return [x.strip() for x in re.split(r"[;|]", s or "") if x.strip()]


def _int(s) -> int | None:
    s = str(s or "").strip()
    return int(s[:4]) if s[:4].isdigit() else None


def _float(s) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# Columns recognised (case-insensitive); any extras are ignored.
EXPORT_COLUMNS = ["media_type", "title", "artist", "author", "narrator", "developer", "director",
                  "year", "format", "label", "publisher", "studio", "platforms", "tracklist",
                  "genres", "rating", "barcode", "isbn", "pages", "duration", "cover_url", "intro"]

_DEFAULT_FMT = {"music": "CD", "book": "Paperback", "game": "PC", "audiobook": "Audible"}


def _row_to_item(row: dict) -> dict:
    r = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
    artist, author, developer = r.get("artist"), r.get("author"), r.get("developer")
    narrator = r.get("narrator")
    mt = ((r.get("media_type") or "").lower()
          or ("audiobook" if narrator else "game" if developer else "book" if author
              else "music" if artist else "movie"))
    title = r.get("title") or r.get("album") or r.get("name")
    if not title:
        return {}
    year, fmt = _int(r.get("year")), (r.get("format") or None)
    cover = r.get("cover_url") or None
    genres = _split(r.get("genres"))
    intro = r.get("intro") or None
    common = {
        "media_type": mt, "title": title, "year": year, "format": fmt,
        "genres": genres, "rating": _float(r.get("rating")), "intro": intro, "overview": intro,
        "poster": cover, "images": [cover] if cover else [],
        "source": {"name": "csv", "url": None},
        "resale": estimate(title, year, fmt or _DEFAULT_FMT.get(mt, "DVD"),
                           _float(r.get("rating")), "com", media_type=mt),
        "seen": False, "date_seen": None, "added_at": _now(),
    }
    if mt == "music":
        common.update({
            "id": _slug(f"{artist}-{title}-{year}"), "artist": artist or None,
            "label": r.get("label") or None, "tracklist": _split(r.get("tracklist")),
            "barcode": r.get("barcode") or None, "catalog_no": r.get("catalog_no") or None,
            "disc_count": 1, "listen": listen_links(artist, title),
        })
    elif mt == "book":
        common.update({
            "id": _slug(f"{author}-{title}-{year}"), "author": author or None,
            "publisher": r.get("publisher") or None, "isbn": r.get("isbn") or None,
            "page_count": _int(r.get("pages") or r.get("page_count")),
            "read": read_links(author, title),
        })
    elif mt == "game":
        common.update({
            "id": _slug(f"{title}-{year}"), "developer": developer or None,
            "publisher": r.get("publisher") or None, "platforms": _split(r.get("platforms")),
            "play": play_links(title, fmt),
        })
    elif mt == "audiobook":
        common.update({
            "id": _slug(f"{author}-{title}-{year}"), "author": author or None,
            "narrator": narrator or None, "publisher": r.get("publisher") or None,
            "isbn": r.get("isbn") or None, "duration": _int(r.get("duration")),
            "listen": hear_links(author, title),
        })
    else:
        common.update({
            "id": _slug(f"{title}-{year}"), "director": r.get("director") or None,
            "actors": _split(r.get("cast") or r.get("actors")),
            "studio": r.get("studio") or r.get("label") or None,
            "language": r.get("language") or None, "runtime": _int(r.get("runtime")),
            "category": "Film",
        })
    return common


def _enrich(cfg, item: dict, log) -> bool:
    """Fill missing fields + cover art from the configured provider (online)."""
    from .metadata import get_metadata_provider
    try:
        if item["media_type"] == "music":
            meta = get_metadata_provider(cfg, "music").lookup(
                item["title"], item.get("year"), artist=item.get("artist"))
            if not meta.matched:
                return False
            item["artist"] = item.get("artist") or meta.artist
            item["label"] = item.get("label") or meta.label
            item["tracklist"] = item.get("tracklist") or meta.tracklist
            item["barcode"] = item.get("barcode") or meta.barcode
            cover = meta.cover_url
        elif item["media_type"] == "book":
            meta = get_metadata_provider(cfg, "book").lookup(
                item["title"], item.get("year"), author=item.get("author"))
            if not meta.matched:
                return False
            item["author"] = item.get("author") or meta.author
            item["publisher"] = item.get("publisher") or meta.publisher
            item["isbn"] = item.get("isbn") or meta.isbn
            item["page_count"] = item.get("page_count") or meta.page_count
            cover = meta.cover_url
        elif item["media_type"] == "game":
            meta = get_metadata_provider(cfg, "game").lookup(item["title"], item.get("year"))
            if not meta.matched:
                return False
            item["developer"] = item.get("developer") or meta.developer
            item["publisher"] = item.get("publisher") or meta.publisher
            item["platforms"] = item.get("platforms") or meta.platforms
            cover = meta.cover_url
        elif item["media_type"] == "audiobook":
            meta = get_metadata_provider(cfg, "audiobook").lookup(
                item["title"], item.get("year"), author=item.get("author"))
            if not meta.matched:
                return False
            item["author"] = item.get("author") or meta.author
            item["narrator"] = item.get("narrator") or meta.narrator
            item["publisher"] = item.get("publisher") or meta.publisher
            item["isbn"] = item.get("isbn") or meta.isbn
            item["duration"] = item.get("duration") or meta.duration
            cover = meta.cover_url
        else:
            meta = get_metadata_provider(cfg).lookup(item["title"], item.get("year"))
            if not meta.matched:
                return False
            item["director"] = item.get("director") or meta.director
            item["actors"] = item.get("actors") or meta.actors
            item["studio"] = item.get("studio") or meta.studio
            cover = meta.poster_url
        item["year"] = item.get("year") or meta.year
        item["genres"] = item.get("genres") or meta.genres
        item["rating"] = item.get("rating") or meta.rating
        item["overview"] = item.get("overview") or getattr(meta, "overview", None)
        if cover and not item.get("poster"):
            item["poster"], item["images"] = cover, [cover]
        item["source"] = {"name": meta.source, "url": meta.source_url}
        return True
    except Exception as exc:                       # never let one bad row kill the import
        log(f"  enrich failed for {item['title']!r}: {exc}")
        return False


def import_csv(cfg, store, path: Path, online: bool, log) -> tuple[int, int]:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    added = enriched = 0
    for row in rows:
        item = _row_to_item(row)
        if not item:
            continue
        if online and _enrich(cfg, item, log):
            enriched += 1
        existed = store.find_movie(item["id"]) is not None
        store.upsert_movie(item)
        store.record(f"csv-{item['id']}", f"(csv) {item['title']}", "identified", item["id"], _now())
        if not existed:
            store.events.add("add", item["id"])
        added += 1
    store.events.add("import", n=added, src="csv")
    log(f"CSV import: {added} item(s) added" + (f", {enriched} enriched online" if online else ""))
    return added, enriched


def export_csv(store, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for m in store.collection:
            w.writerow({
                "media_type": m.get("media_type", "movie"), "title": m.get("title"),
                "artist": m.get("artist"), "author": m.get("author"),
                "narrator": m.get("narrator"),
                "developer": m.get("developer"), "director": m.get("director"),
                "year": m.get("year"), "format": m.get("format"), "label": m.get("label"),
                "publisher": m.get("publisher"), "studio": m.get("studio"),
                "platforms": "; ".join(m.get("platforms") or []),
                "tracklist": "; ".join(m.get("tracklist") or []),
                "genres": "; ".join(m.get("genres") or []), "rating": m.get("rating"),
                "barcode": m.get("barcode"), "isbn": m.get("isbn"), "pages": m.get("page_count"),
                "duration": m.get("duration"),
                "cover_url": m.get("poster"), "intro": m.get("intro"),
            })
    return len(store.collection)
