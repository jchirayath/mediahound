"""MusicBrainz metadata provider (open, CC0, no API key) + Cover Art Archive cover images.

MusicBrainz asks clients to send a descriptive User-Agent and stay under ~1 request/second;
this provider does both. Failures degrade to MusicMeta(False) — never crash a build.
"""
from __future__ import annotations

import time

import requests

from .base import MusicMeta

_WS = "https://musicbrainz.org/ws/2"
_CAA = "https://coverartarchive.org"
_UA = "MediaHound/0.2 ( https://github.com/jchirayath/mediahound )"


class MusicBrainzProvider:
    name = "musicbrainz"
    media_type = "music"

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = _UA

    def _get(self, url: str, **params) -> dict:
        wait = 1.0 - (time.monotonic() - self._last)   # be polite: ≥1s between calls
        if wait > 0:
            time.sleep(wait)
        params.setdefault("fmt", "json")
        r = self.session.get(url, params=params, timeout=30)
        self._last = time.monotonic()
        r.raise_for_status()
        return r.json()

    def lookup(self, title: str, year: int | None = None, artist: str | None = None) -> MusicMeta:
        if not title:
            return MusicMeta(False)
        terms = [f'release:"{title}"']
        if artist:
            terms.append(f'artist:"{artist}"')
        try:
            res = self._get(f"{_WS}/release", query=" AND ".join(terms), limit=1)
            releases = res.get("releases", [])
            if not releases:
                return MusicMeta(False)
            rid = releases[0]["id"]
            d = self._get(f"{_WS}/release/{rid}", inc="artist-credits+labels+recordings+genres")
        except (requests.RequestException, ValueError):
            return MusicMeta(False)
        return self._parse(rid, d, year)

    def lookup_by_barcode(self, upc: str, year: int | None = None) -> MusicMeta:
        """Resolve a UPC/EAN barcode to the exact release (MusicBrainz supports barcode search)."""
        upc = (upc or "").strip()
        if not upc:
            return MusicMeta(False)
        try:
            res = self._get(f"{_WS}/release", query=f"barcode:{upc}", limit=1)
            releases = res.get("releases", [])
            if not releases:
                return MusicMeta(False)
            rid = releases[0]["id"]
            d = self._get(f"{_WS}/release/{rid}", inc="artist-credits+labels+recordings+genres")
        except (requests.RequestException, ValueError):
            return MusicMeta(False)
        return self._parse(rid, d, year)

    def _parse(self, rid: str, d: dict, year_hint: int | None) -> MusicMeta:
        artist = "".join(
            (c.get("name") or "") + (c.get("joinphrase") or "")
            for c in d.get("artist-credit", [])
        ).strip() or None

        label = catalog = None
        li = d.get("label-info") or []
        if li:
            label = (li[0].get("label") or {}).get("name")
            catalog = li[0].get("catalog-number")

        media = d.get("media") or []
        fmt = media[0].get("format") if media else None
        tracklist = [t.get("title") for m in media for t in (m.get("tracks") or []) if t.get("title")]
        genres = [g["name"] for g in sorted(d.get("genres", []),
                                            key=lambda g: g.get("count", 0), reverse=True)[:4]
                  if g.get("name")]

        date = (d.get("date") or "")[:4]
        return MusicMeta(
            matched=True,
            source="musicbrainz",
            source_id=rid,
            title=d.get("title"),
            artist=artist,
            year=int(date) if date.isdigit() else year_hint,
            genres=genres,
            label=label,
            catalog_no=catalog,
            barcode=d.get("barcode") or None,
            format=fmt,
            disc_count=len(media) or None,
            tracklist=tracklist,
            cover_url=f"{_CAA}/release/{rid}/front-500",
            source_url=f"https://musicbrainz.org/release/{rid}",
            raw={"id": rid},
        )
