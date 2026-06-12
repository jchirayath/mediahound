"""Import a Discogs user's collection into the MediaHound catalog.

Many vinyl/CD owners already curate their collection on Discogs. `import_collection()` pulls a
user's public collection (folder 0 = "All"), maps each release to a `media_type=music` catalog
item — the same shape the CSV importer produces — and (optionally) enriches it with the full
release record (tracklist, exact barcode, styles). Nothing is written back to Discogs.

A personal access token raises the rate limit; for a *public* collection it is optional.
"""
from __future__ import annotations

import re
import time
from datetime import UTC, datetime

import requests

from . import __version__
from .links import listen_links
from .metadata.discogs import DiscogsProvider
from .resale import estimate

_API = "https://api.discogs.com"
_UA = f"MediaHound/{__version__} ( https://github.com/jchirayath/mediahound )"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-") or "item"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _fmt(formats: list) -> str:
    name = formats[0].get("name") if formats else None
    return DiscogsProvider._fmt(name) or "Vinyl"


def _basic_item(bi: dict, tld: str) -> dict:
    """Map a collection entry's `basic_information` block to a catalog item."""
    rid = str(bi.get("id") or "")
    title = bi.get("title") or "Untitled"
    artist = ", ".join(a.get("name", "").strip() for a in bi.get("artists", []) if a.get("name")) or None
    artist = re.sub(r"\s*\(\d+\)$", "", artist) if artist else None     # strip Discogs "(2)" disambiguators
    year = bi.get("year") or None
    labels = bi.get("labels") or []
    fmt = _fmt(bi.get("formats") or [])
    cover = bi.get("cover_image") or bi.get("thumb") or None
    genres = (bi.get("genres") or []) + (bi.get("styles") or [])
    return {
        "id": _slug(f"{artist or ''}-{title}-{year or rid}"),
        "media_type": "music", "title": title, "artist": artist, "year": year,
        "format": fmt, "label": labels[0].get("name") if labels else None,
        "catalog_no": labels[0].get("catno") if labels else None,
        "genres": genres[:4], "tracklist": [], "disc_count": 1, "rating": None,
        "barcode": None, "discogs_release_id": rid,
        "poster": cover, "images": [cover] if cover else [],
        "intro": f"{artist} — {title}." if artist else title, "overview": None,
        "listen": listen_links(artist or "", title),
        "source": {"name": "discogs", "url": f"https://www.discogs.com/release/{rid}"},
        "resale": estimate(f"{artist or ''} {title}".strip(), year, fmt, None, tld),
        "source_image": f"(discogs) {title}", "confidence": 0.99,
        "seen": False, "date_seen": None, "added_at": _now(),
    }


def import_collection(cfg, store, username: str, token: str | None = None,
                      online: bool = True, log=print) -> tuple[int, int]:
    """Fetch `username`'s Discogs collection → catalog items. With online=True, enrich each via
    the full release endpoint (tracklist + barcode). Returns (added, enriched)."""
    prov = DiscogsProvider(token=token)
    tld = cfg.resale.get("ebay_tld", "com")
    session = requests.Session()
    session.headers["User-Agent"] = _UA
    if prov.token:
        session.headers["Authorization"] = f"Discogs token={prov.token}"

    added = enriched = 0
    page, pages = 1, 1
    last = 0.0
    while page <= pages:
        wait = 1.0 - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        url = f"{_API}/users/{username}/collection/folders/0/releases"
        r = session.get(url, params={"page": page, "per_page": 100}, timeout=30)
        last = time.monotonic()
        if r.status_code == 404:
            raise RuntimeError(f"Discogs user {username!r} not found (or collection is private).")
        r.raise_for_status()
        body = r.json()
        pages = (body.get("pagination") or {}).get("pages", 1)
        for entry in body.get("releases", []):
            bi = entry.get("basic_information") or {}
            item = _basic_item(bi, tld)
            if online and item.get("discogs_release_id"):
                meta = prov.release(item["discogs_release_id"], item.get("year"))
                if meta.matched:
                    item["tracklist"] = meta.tracklist or item["tracklist"]
                    item["barcode"] = meta.barcode
                    item["rating"] = meta.rating
                    if meta.genres:
                        item["genres"] = meta.genres
                    enriched += 1
            store.upsert_movie(item)
            store.record(f"discogs-{item['id']}", item["source_image"], "identified", item["id"], _now())
            added += 1
        log(f"  Discogs: imported page {page}/{pages} ({added} so far)")
        page += 1
    log(f"Discogs import: {added} release(s) added" + (f", {enriched} enriched" if online else ""))
    return added, enriched
