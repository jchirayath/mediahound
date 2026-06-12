"""Audiobook metadata provider (zero-key) — Open Library for the book, LibriVox for the audio.

An audiobook is a book you listen to, so its core metadata (title, author, year, publisher, ISBN,
cover) comes from **Open Library** — exactly like a printed book. The audiobook-specific bits —
**total duration** and an audio **overview** — come from the **LibriVox** public catalogue when the
title is a public-domain recording (best-effort; many commercial titles aren't in any free DB, so
`narrator`/`duration` then stay empty and are filled from the cover/CSV/manual edit). Both APIs are
keyless. Failures degrade to AudiobookMeta(False); a partial match (book but no LibriVox) still wins.
"""
from __future__ import annotations

import requests

from .. import __version__
from .base import AudiobookMeta
from .openlibrary import OpenLibraryProvider

_LIBRIVOX = "https://librivox.org/api/feed/audiobooks"
_UA = f"MediaHound/{__version__} ( https://github.com/jchirayath/mediahound )"


class AudiobookProvider:
    name = "openlibrary+librivox"
    media_type = "audiobook"

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}
        self.books = OpenLibraryProvider(cfg)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = _UA

    def lookup(self, title: str, year: int | None = None, author: str | None = None,
               narrator: str | None = None) -> AudiobookMeta:
        if not title:
            return AudiobookMeta(False)
        book = self.books.lookup(title, year, author)          # author/cover/publisher/isbn/genres
        lv = self._librivox(title)                             # duration/overview (public domain only)
        if not getattr(book, "matched", False) and not lv:
            return AudiobookMeta(False)
        src = "+".join(s for s in (("openlibrary" if book.matched else None),
                                   ("librivox" if lv else None)) if s)
        return AudiobookMeta(
            matched=True, source=src or "manual",
            source_id=(book.source_id if book.matched else (lv or {}).get("id", "")),
            title=(book.title if book.matched else title),
            author=author or (book.author if book.matched else None),
            narrator=narrator,
            year=(book.year if book.matched else year) or (lv or {}).get("year") or year,
            genres=book.genres if book.matched else [],
            publisher=book.publisher if book.matched else None,
            isbn=book.isbn if book.matched else None,
            duration=(lv or {}).get("minutes"),
            overview=(lv or {}).get("overview"),
            cover_url=book.cover_url if book.matched else None,
            source_url=(lv or {}).get("url") or (book.source_url if book.matched else None),
            raw={"librivox": bool(lv)},
        )

    def _librivox(self, title: str) -> dict | None:
        """Best-effort: the LibriVox catalogue (public-domain audiobooks) → duration + overview."""
        try:
            r = self.session.get(_LIBRIVOX, params={"title": title, "format": "json"}, timeout=20)
            if r.status_code == 404:                            # LibriVox 404s on "no results"
                return None
            r.raise_for_status()
            books = (r.json() or {}).get("books") or []
        except (requests.RequestException, ValueError):
            return None
        if not books:
            return None
        b = books[0]
        secs = b.get("totaltimesecs")
        yr = (str(b.get("copyright_year") or "")[:4])
        return {
            "id": str(b.get("id") or ""),
            "minutes": (int(secs) // 60) if str(secs).isdigit() else None,
            "overview": (b.get("description") or "").strip() or None,
            "year": int(yr) if yr.isdigit() else None,
            "url": b.get("url_librivox") or None,
        }
