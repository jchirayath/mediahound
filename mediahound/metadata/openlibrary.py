"""Open Library metadata provider (open data, CC0, no API key) for books.

Open Library resolves a **book** by ISBN — or by title + author — to title, author(s), publish year,
publisher, page count, subjects, and a cover image, with **no key required** (matching MediaHound's
zero-key default). It asks clients to send a descriptive User-Agent. Failures degrade to
BookMeta(False) — never crash a build.
"""
from __future__ import annotations

import requests

from .. import __version__
from .base import BookMeta

_OL = "https://openlibrary.org"
_COVERS = "https://covers.openlibrary.org/b"
_UA = f"MediaHound/{__version__} ( https://github.com/jchirayath/mediahound )"


class OpenLibraryProvider:
    name = "openlibrary"
    media_type = "book"

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = _UA

    def _get(self, url: str, **params) -> dict:
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    # -- public API --------------------------------------------------------
    def lookup(self, title: str, year: int | None = None, author: str | None = None) -> BookMeta:
        if not title:
            return BookMeta(False)
        params = {"title": title, "limit": 1,
                  "fields": "title,author_name,first_publish_year,cover_i,cover_edition_key,"
                            "isbn,number_of_pages_median,publisher,subject,key"}
        if author:
            params["author"] = author
        try:
            res = self._get(f"{_OL}/search.json", **params)
        except (requests.RequestException, ValueError):
            return BookMeta(False)
        docs = res.get("docs") or []
        if not docs:
            return BookMeta(False)
        return self._from_search(docs[0], year)

    def lookup_by_isbn(self, isbn: str, year: int | None = None) -> BookMeta:
        isbn = (isbn or "").replace("-", "").strip()
        if not isbn:
            return BookMeta(False)
        try:
            res = self._get(f"{_OL}/api/books", bibkeys=f"ISBN:{isbn}", format="json", jscmd="data")
        except (requests.RequestException, ValueError):
            return BookMeta(False)
        rec = res.get(f"ISBN:{isbn}")
        if not rec:
            return BookMeta(False)
        return self._from_isbn(isbn, rec, year)

    # -- parsing -----------------------------------------------------------
    def _from_search(self, d: dict, year_hint: int | None) -> BookMeta:
        authors = d.get("author_name") or []
        cover = None
        if d.get("cover_i"):
            cover = f"{_COVERS}/id/{d['cover_i']}-L.jpg"
        elif d.get("isbn"):
            cover = f"{_COVERS}/isbn/{d['isbn'][0]}-L.jpg"
        return BookMeta(
            matched=True, source="openlibrary", source_id=str(d.get("key") or ""),
            title=d.get("title"),
            author=", ".join(authors[:3]) or None,
            year=d.get("first_publish_year") or year_hint,
            genres=[s for s in (d.get("subject") or [])[:4] if s],
            publisher=(d.get("publisher") or [None])[0],
            isbn=(d.get("isbn") or [None])[0],
            page_count=d.get("number_of_pages_median"),
            cover_url=cover,
            source_url=f"{_OL}{d['key']}" if d.get("key") else None,
            raw={"key": d.get("key")},
        )

    def _from_isbn(self, isbn: str, rec: dict, year_hint: int | None) -> BookMeta:
        authors = [a.get("name") for a in (rec.get("authors") or []) if a.get("name")]
        publishers = [p.get("name") for p in (rec.get("publishers") or []) if p.get("name")]
        date = str(rec.get("publish_date") or "")
        ym = "".join(c for c in date if c.isdigit())[-4:] if any(c.isdigit() for c in date) else ""
        cover = (rec.get("cover") or {}).get("large") or f"{_COVERS}/isbn/{isbn}-L.jpg"
        return BookMeta(
            matched=True, source="openlibrary",
            source_id=str((rec.get("identifiers") or {}).get("openlibrary", [""])[0] or isbn),
            title=rec.get("title"),
            author=", ".join(authors[:3]) or None,
            year=int(ym) if ym.isdigit() and len(ym) == 4 else year_hint,
            genres=[s.get("name") for s in (rec.get("subjects") or [])[:4] if s.get("name")],
            publisher=publishers[0] if publishers else None,
            isbn=isbn,
            page_count=rec.get("number_of_pages"),
            cover_url=cover,
            source_url=rec.get("url"),
            raw={"isbn": isbn},
        )
