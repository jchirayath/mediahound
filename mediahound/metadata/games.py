"""Video-game metadata provider via the Wikidata Query Service (SPARQL) — open data, CC0, no key.

Resolves a game by title to developer, publisher, year, genres, platform(s) and (when present) a
cover/key-art image, with **no API key** (MediaHound's zero-key default). A paid RAWG/IGDB provider
can be added later for richer art; this gives a keyless baseline. Failures degrade to GameMeta(False).

Security: the title is **escaped** before being interpolated into SPARQL (no query injection), and the
provider only issues a read-only SELECT to the public endpoint.
"""
from __future__ import annotations

import requests

from .. import __version__
from .base import GameMeta

_SPARQL = "https://query.wikidata.org/sparql"
_UA = f"MediaHound/{__version__} ( https://github.com/jchirayath/mediahound )"

# Map Wikidata platform labels to MediaHound's compact platform buckets (the item's `format`).
_BUCKETS = (
    ("switch", "Switch"), ("playstation 5", "PS5"), ("playstation 4", "PS4"),
    ("xbox", "Xbox"), ("windows", "PC"), ("linux", "PC"), ("macos", "PC"), ("steam", "PC"),
    ("playstation 3", "Retro"), ("playstation 2", "Retro"), ("playstation portable", "Retro"),
    ("game boy", "Retro"), ("nintendo entertainment", "Retro"), ("super nintendo", "Retro"),
    ("nintendo 64", "Retro"), ("gamecube", "Retro"), ("genesis", "Retro"), ("mega drive", "Retro"),
    ("wii", "Retro"), ("nintendo ds", "Retro"), ("nintendo 3ds", "Retro"),
)


def _bucket(label: str) -> str:
    low = (label or "").lower()
    for needle, bucket in _BUCKETS:
        if needle in low:
            return bucket
    return label or "Unknown"


def _esc(s: str) -> str:
    """Escape a string for safe interpolation into a SPARQL string literal (no injection)."""
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    return "".join(c for c in s if ord(c) >= 32)        # drop control chars / newlines


class GameProvider:
    name = "wikidata-games"
    media_type = "game"

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = _UA
        self.session.headers["Accept"] = "application/sparql-results+json"

    def lookup(self, title: str, year: int | None = None, **_) -> GameMeta:
        if not title:
            return GameMeta(False)
        q = (
            "SELECT ?item ?itemLabel ?devLabel ?pubLabel ?genreLabel ?platformLabel ?date ?image WHERE {"
            "  ?item wdt:P31 wd:Q7889 ; rdfs:label ?l ."
            f'  FILTER(LANG(?l)="en" && LCASE(STR(?l))=LCASE("{_esc(title)}"))'
            "  OPTIONAL { ?item wdt:P178 ?dev. ?dev rdfs:label ?devLabel. FILTER(LANG(?devLabel)=\"en\") }"
            "  OPTIONAL { ?item wdt:P123 ?pub. ?pub rdfs:label ?pubLabel. FILTER(LANG(?pubLabel)=\"en\") }"
            "  OPTIONAL { ?item wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(LANG(?genreLabel)=\"en\") }"
            "  OPTIONAL { ?item wdt:P400 ?platform. ?platform rdfs:label ?platformLabel. FILTER(LANG(?platformLabel)=\"en\") }"
            "  OPTIONAL { ?item wdt:P577 ?date. }"
            "  OPTIONAL { ?item wdt:P18 ?image. }"
            "  ?item rdfs:label ?itemLabel. FILTER(LANG(?itemLabel)=\"en\")"
            "} LIMIT 60"
        )
        try:
            r = self.session.get(_SPARQL, params={"query": q, "format": "json"}, timeout=30)
            r.raise_for_status()
            rows = (r.json().get("results") or {}).get("bindings") or []
        except (requests.RequestException, ValueError):
            return GameMeta(False)
        if not rows:
            return GameMeta(False)
        return self._parse(rows, year)

    def _parse(self, rows: list[dict], year_hint: int | None) -> GameMeta:
        def val(row, k):
            return (row.get(k) or {}).get("value")

        item = val(rows[0], "item")
        # keep only the rows for the first matched game, then aggregate its multi-valued fields
        rows = [r for r in rows if val(r, "item") == item]
        title = val(rows[0], "itemLabel")
        devs = _uniq(val(r, "devLabel") for r in rows)
        pubs = _uniq(val(r, "pubLabel") for r in rows)
        genres = _uniq(val(r, "genreLabel") for r in rows)
        platforms = _uniq(val(r, "platformLabel") for r in rows)
        dates = [val(r, "date") for r in rows if val(r, "date")]
        year = None
        for d in dates:
            yr = (d or "")[:4]
            if yr.isdigit():
                year = min(year or 9999, int(yr))
        image = next((val(r, "image") for r in rows if val(r, "image")), None)
        buckets = _uniq(_bucket(p) for p in platforms)
        return GameMeta(
            matched=True, source="wikidata", source_id=(item or "").rsplit("/", 1)[-1],
            title=title, developer=devs[0] if devs else None,
            publisher=pubs[0] if pubs else None, year=year or year_hint,
            genres=genres[:4], platforms=buckets,
            format=buckets[0] if buckets else "PC",
            cover_url=(image + "?width=500") if image else None,
            source_url=item,
            raw={"qid": (item or "").rsplit("/", 1)[-1]},
        )


def _uniq(seq) -> list:
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out
