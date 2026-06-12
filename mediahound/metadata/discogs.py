"""Discogs metadata provider (records & CDs) + price suggestions.

Discogs is *the* database/marketplace for physical music. This provider resolves a release by
title/artist or by **barcode** to rich metadata (exact pressing, label, catalog #, styles,
tracklist, cover). A personal access token (Discogs → Settings → Developers) raises the rate
limit and is **required** for marketplace price suggestions; metadata search works without one.

Etiquette: a descriptive User-Agent and ≤1 request/second (Discogs asks for ≤60/min). Failures
degrade to MusicMeta(False) / None — they never crash a build.
"""
from __future__ import annotations

import os
import re
import time

import requests

from .. import __version__
from .base import MusicMeta

_DISAMBIG_RE = re.compile(r"\s*\(\d+\)$")        # Discogs appends "(2)" to disambiguate same-named artists

_API = "https://api.discogs.com"
_UA = f"MediaHound/{__version__} ( https://github.com/jchirayath/mediahound )"


class DiscogsProvider:
    name = "discogs"
    media_type = "music"

    def __init__(self, cfg: dict | None = None, token: str | None = None):
        self.cfg = cfg or {}
        self.token = token or os.environ.get("DISCOGS_TOKEN") or self.cfg.get("token")
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = _UA
        if self.token:
            self.session.headers["Authorization"] = f"Discogs token={self.token}"

    # -- low-level ---------------------------------------------------------
    def _get(self, path: str, **params) -> dict:
        wait = 1.0 - (time.monotonic() - self._last)    # ≤1 req/s — be polite
        if wait > 0:
            time.sleep(wait)
        r = self.session.get(f"{_API}{path}", params=params, timeout=30)
        self._last = time.monotonic()
        r.raise_for_status()
        return r.json()

    def _search(self, **params) -> str | None:
        params.setdefault("type", "release")
        params.setdefault("per_page", 1)
        res = self._get("/database/search", **params)
        results = res.get("results") or []
        return str(results[0]["id"]) if results else None

    # -- public API --------------------------------------------------------
    def lookup(self, title: str, year: int | None = None, artist: str | None = None) -> MusicMeta:
        if not title:
            return MusicMeta(False)
        try:
            params = {"release_title": title}
            if artist:
                params["artist"] = artist
            rid = self._search(**params)
            if not rid:
                return MusicMeta(False)
            return self.release(rid, year)
        except (requests.RequestException, ValueError, KeyError):
            return MusicMeta(False)

    def lookup_by_barcode(self, upc: str, year: int | None = None) -> MusicMeta:
        if not upc:
            return MusicMeta(False)
        try:
            rid = self._search(barcode=str(upc).strip())
            if not rid:
                return MusicMeta(False)
            return self.release(rid, year)
        except (requests.RequestException, ValueError, KeyError):
            return MusicMeta(False)

    def release(self, release_id: str, year_hint: int | None = None) -> MusicMeta:
        d = self._get(f"/releases/{release_id}")
        return self._parse(str(release_id), d, year_hint)

    def price_suggestion(self, release_id: str, condition: str = "Very Good Plus (VG+)") -> dict | None:
        """Marketplace price by condition (token required). Returns {value, currency} or None."""
        if not self.token:
            return None
        try:
            d = self._get(f"/marketplace/price_suggestions/{release_id}")
        except (requests.RequestException, ValueError):
            return None
        info = d.get(condition) or next(iter(d.values()), None) if d else None
        if isinstance(info, dict) and "value" in info:
            return {"value": info.get("value"), "currency": info.get("currency")}
        return None

    # -- parsing -----------------------------------------------------------
    def _parse(self, rid: str, d: dict, year_hint: int | None) -> MusicMeta:
        artist = ", ".join(_DISAMBIG_RE.sub("", a.get("name", "").strip())
                           for a in d.get("artists", []) if a.get("name")) or None
        labels = d.get("labels") or []
        label = labels[0].get("name") if labels else None
        catalog = labels[0].get("catno") if labels else None

        formats = d.get("formats") or []
        fmt = self._fmt(formats[0].get("name") if formats else None)
        disc_count = None
        if formats and str(formats[0].get("qty") or "").isdigit():
            disc_count = int(formats[0]["qty"]) or None

        tracklist = [t.get("title") for t in d.get("tracklist", [])
                     if t.get("title") and t.get("type_", "track") == "track"]
        genres = (d.get("genres") or []) + (d.get("styles") or [])

        barcode = None
        for ident in d.get("identifiers", []):
            if (ident.get("type") or "").lower() == "barcode":
                barcode = (ident.get("value") or "").replace(" ", "") or None
                break

        images = d.get("images") or []
        cover = None
        if images:
            primary = next((im for im in images if im.get("type") == "primary"), images[0])
            cover = primary.get("uri") or primary.get("resource_url")

        rating = None
        comm = d.get("community") or {}
        if isinstance(comm.get("rating"), dict) and comm["rating"].get("average"):
            rating = round(float(comm["rating"]["average"]) * 2, 1)   # Discogs 0–5 → 0–10 scale

        return MusicMeta(
            matched=True,
            source="discogs",
            source_id=rid,
            title=d.get("title"),
            artist=artist,
            year=d.get("year") or year_hint,
            genres=genres[:4],
            label=label,
            catalog_no=catalog,
            barcode=barcode,
            format=fmt,
            disc_count=disc_count,
            tracklist=tracklist,
            rating=rating,
            cover_url=cover,
            source_url=d.get("uri") or f"https://www.discogs.com/release/{rid}",
            raw={"id": rid, "release_id": rid},
        )

    @staticmethod
    def _fmt(name: str | None) -> str | None:
        if not name:
            return None
        n = name.lower()
        if "vinyl" in n or n == "lp":
            return "Vinyl"
        if "cassette" in n:
            return "Cassette"
        if "cd" in n:
            return "CD"
        return name
