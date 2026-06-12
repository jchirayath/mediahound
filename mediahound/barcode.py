"""Barcode / UPC identification — the single biggest accuracy + speed win.

A barcode on the back of a case identifies the **exact** release, sidestepping fuzzy OCR. We
decode it locally, then resolve it:

  • **music** → MusicBrainz / Discogs barcode search → the exact release (very accurate, free).
  • **movie** → UPCItemDB resolves the UPC to a product *name*, which we feed into the existing
    identify-by-title path (no new movie pipeline).

Decoding is local; the UPC→release/title lookups are network calls, so callers gate them behind
`--online` exactly like other enrichment. Decoding needs the optional `mediahound[barcode]` extra
(`zxing-cpp`, a pip wheel with no system library); without it, `decode_image()` returns [].
"""
from __future__ import annotations

from pathlib import Path

from .config import Config


def decode_image(path: str | Path) -> list[str]:
    """Decode every UPC-A / EAN-13 barcode found in an image. Returns [] if the optional
    `zxing-cpp` decoder isn't installed or nothing decodes (never raises)."""
    try:
        import zxingcpp  # optional: mediahound[barcode]
    except ImportError:
        return []
    try:
        from PIL import Image
        with Image.open(path) as im:
            results = zxingcpp.read_barcodes(im.convert("RGB"))
    except Exception:                                    # noqa: BLE001 - bad image / decoder error
        return []
    out: list[str] = []
    for r in results:
        text = (getattr(r, "text", "") or "").strip()
        if text and text.isdigit() and text not in out:  # keep only numeric product codes
            out.append(text)
    return out


def _music_provider(cfg: Config):
    """The music provider to use for a barcode — the configured one if it supports barcode
    search (MusicBrainz / Discogs both do), else MusicBrainz."""
    from .metadata import get_metadata_provider
    prov = get_metadata_provider(cfg, "music")
    if hasattr(prov, "lookup_by_barcode"):
        return prov
    from .metadata.musicbrainz import MusicBrainzProvider
    return MusicBrainzProvider()


def is_isbn(code: str) -> bool:
    """An EAN-13 in the Bookland range (978/979) is an ISBN — i.e. a book, unambiguously."""
    code = (code or "").strip()
    return len(code) == 13 and code.isdigit() and code[:3] in ("978", "979")


def lookup(cfg: Config, upc: str, media_type: str = "music") -> dict | None:
    """Resolve a UPC to a release (music) or a product title (movie). Returns a dict:
      music → {media_type, upc, title, artist, year, meta:<MusicMeta>}
      movie → {media_type, upc, title, year:None}
    or None if nothing matched. Makes network calls — gate behind --online."""
    upc = (upc or "").strip()
    if not upc:
        return None
    # An ISBN (978/979) is always a book, regardless of the requested media_type.
    if media_type == "book" or is_isbn(upc):
        from .metadata import get_metadata_provider
        meta = get_metadata_provider(cfg, "book").lookup_by_isbn(upc)
        if not getattr(meta, "matched", False):
            return None
        return {"media_type": "book", "upc": upc, "title": meta.title,
                "author": meta.author, "year": meta.year, "meta": meta}
    if media_type == "music":
        meta = _music_provider(cfg).lookup_by_barcode(upc)
        if not getattr(meta, "matched", False):
            return None
        return {"media_type": "music", "upc": upc, "title": meta.title,
                "artist": meta.artist, "year": meta.year, "meta": meta}
    # movie: UPC → product name → existing identify-by-title path
    from .metadata.upcitemdb import UPCItemDBProvider
    title = UPCItemDBProvider().title_for(upc)
    if not title:
        return None
    return {"media_type": "movie", "upc": upc, "title": title, "year": None}


def music_item_from_meta(cfg: Config, meta, upc: str | None = None) -> dict:
    """Build a catalog item (music) from a resolved MusicMeta — used when a barcode is scanned
    without a cover photo (the cover comes from the release's online art)."""
    import re
    from datetime import UTC, datetime

    from .links import listen_links
    from .resale import estimate

    slug = re.sub(r"[^a-z0-9]+", "-",
                  f"{meta.artist or ''}-{meta.title}-{meta.year or (upc or '')[:6]}".lower()).strip("-") or "item"
    fmt = meta.format or "CD"
    cover = meta.cover_url
    return {
        "id": slug, "media_type": "music", "title": meta.title, "artist": meta.artist,
        "year": meta.year, "format": fmt, "label": meta.label, "genres": meta.genres,
        "rating": meta.rating, "tracklist": meta.tracklist, "disc_count": meta.disc_count,
        "barcode": meta.barcode or upc, "catalog_no": meta.catalog_no,
        "discogs_release_id": (meta.raw or {}).get("release_id"),
        "intro": f"{meta.artist} — {meta.title}." if meta.artist else meta.title,
        "overview": meta.overview, "poster": cover, "images": [cover] if cover else [],
        "listen": listen_links(meta.artist or "", meta.title),
        "source": {"name": meta.source, "url": meta.source_url},
        "resale": estimate(f"{meta.artist or ''} {meta.title}".strip(), meta.year, fmt,
                           meta.rating, cfg.resale.get("ebay_tld", "com")),
        "source_image": f"(barcode {upc})" if upc else f"(barcode) {meta.title}",
        "confidence": 0.99, "seen": False, "date_seen": None,
        "added_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def book_item_from_meta(cfg: Config, meta, isbn: str | None = None) -> dict:
    """Build a catalog item (book) from a resolved BookMeta — used when an ISBN is scanned
    without a cover photo (the cover comes from Open Library)."""
    import re
    from datetime import UTC, datetime

    from .links import read_links
    from .resale import estimate

    slug = re.sub(r"[^a-z0-9]+", "-",
                  f"{meta.author or ''}-{meta.title}-{meta.year or (isbn or '')[:6]}".lower()).strip("-") or "item"
    fmt = meta.format or "Paperback"
    cover = meta.cover_url
    return {
        "id": slug, "media_type": "book", "title": meta.title, "author": meta.author,
        "year": meta.year, "format": fmt, "publisher": meta.publisher, "genres": meta.genres,
        "rating": meta.rating, "page_count": meta.page_count, "isbn": meta.isbn or isbn,
        "series": meta.series,
        "intro": f"{meta.author} — {meta.title}." if meta.author else meta.title,
        "overview": meta.overview, "poster": cover, "images": [cover] if cover else [],
        "read": read_links(meta.author or "", meta.title),
        "source": {"name": meta.source, "url": meta.source_url},
        "resale": estimate(f"{meta.author or ''} {meta.title}".strip(), meta.year, fmt,
                           meta.rating, cfg.resale.get("ebay_tld", "com")),
        "source_image": f"(isbn {isbn})" if isbn else f"(isbn) {meta.title}",
        "confidence": 0.99, "seen": False, "date_seen": None,
        "added_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
