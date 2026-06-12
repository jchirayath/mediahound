"""UPCItemDB product lookup — resolve a UPC/EAN barcode to a product *title*.

Movies have no good free UPC→film database, so for a DVD/Blu-ray barcode we resolve the UPC to
the printed product name (e.g. "The Matrix (Blu-ray)") and feed that into MediaHound's existing
identify-by-title path. No new movie pipeline. The free trial endpoint needs no key (it is
rate-limited); a paid key, if present in `UPCITEMDB_KEY`, uses the higher-quota endpoint.
"""
from __future__ import annotations

import os
import re

import requests

from .. import __version__

_TRIAL = "https://api.upcitemdb.com/prod/trial/lookup"
_PAID = "https://api.upcitemdb.com/prod/v1/lookup"
_UA = f"MediaHound/{__version__} ( https://github.com/jchirayath/mediahound )"

# Strip format/edition noise so the cleaned title feeds the movie identifier well.
_NOISE = re.compile(
    r"\b(blu[- ]?ray|bluray|dvd|4k|uhd|ultra\s*hd|widescreen|full\s*screen|"
    r"collector'?s?\s*edition|special\s*edition|steelbook|digital\s*copy|region\s*\d|"
    r"\d-?disc|disc\s*set|unrated|rated|new|sealed)\b", re.I)


class UPCItemDBProvider:
    name = "upcitemdb"

    def __init__(self, cfg: dict | None = None, key: str | None = None):
        self.cfg = cfg or {}
        self.key = key or os.environ.get("UPCITEMDB_KEY") or self.cfg.get("key")
        self.session = requests.Session()
        self.session.headers["User-Agent"] = _UA

    def lookup_raw(self, upc: str) -> dict | None:
        """Return the first product record for a UPC (title, brand, etc.) or None."""
        upc = (upc or "").strip()
        if not upc:
            return None
        url, headers = _TRIAL, {}
        if self.key:
            url, headers = _PAID, {"user_key": self.key, "key_type": "3scale"}
        try:
            r = self.session.get(url, params={"upc": upc}, headers=headers, timeout=30)
            r.raise_for_status()
            items = (r.json() or {}).get("items") or []
            return items[0] if items else None
        except (requests.RequestException, ValueError):
            return None

    def title_for(self, upc: str) -> str | None:
        """The product title for a UPC, lightly cleaned of format/edition noise."""
        item = self.lookup_raw(upc)
        if not item:
            return None
        return clean_title(item.get("title") or "")


def clean_title(raw: str) -> str | None:
    """Strip edition/format words and trailing punctuation from a product title."""
    t = _NOISE.sub(" ", raw or "")
    t = re.sub(r"[\(\[]\s*[\)\]]", " ", t)        # leftover empty brackets
    t = re.sub(r"[\s\-:;,]+$", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -:[](){}")
    return t or None
