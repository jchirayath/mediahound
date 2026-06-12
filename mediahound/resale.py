"""Estimated used resale value + a link to live sold/completed listings on eBay.

The estimate is a transparent heuristic (no scraping, no key). The link sends the user to
real sold-listing data so they can see actual recent prices.
"""
from __future__ import annotations

from urllib.parse import quote_plus

# Rough baseline used value by format (USD), before rarity adjustments.
_BASE = {"VHS": 8.0, "DVD": 6.0, "Blu-ray": 9.0, "Unknown": 6.0,
         "Hardcover": 8.0, "Paperback": 4.0, "Mass Market": 3.0, "eBook": 2.0, "Audiobook": 6.0,
         # audiobook media: physical sets resell modestly; digital downloads aren't resellable
         "CD": 6.0, "MP3-CD": 7.0, "Cassette": 3.0, "Audible": 0.0, "Digital": 0.0,
         # video games by platform: retro/Switch hold value; PC is mostly digital → low physical resale
         "Switch": 22.0, "PS5": 18.0, "PS4": 12.0, "Xbox": 14.0, "PC": 6.0, "Retro": 20.0}

# platforms whose carts/discs are genuinely collectible (sealed/retro can soar)
_GAME_PLATFORMS = frozenset({"Switch", "PS5", "PS4", "Xbox", "PC", "Retro"})


def estimate(title: str, year: int | None, fmt: str, rating: float | None,
             tld: str = "com", media_type: str | None = None) -> dict:
    base = _BASE.get(fmt, 6.0)
    factor = 1.0
    is_game = media_type == "game" or fmt in _GAME_PLATFORMS

    # Age: older tapes/discs/carts trend collectible; very recent ones are cheap.
    if year:
        if fmt == "VHS" and year < 1995:
            factor *= 1.8
        elif is_game and fmt == "Retro" and year < 2000:
            factor *= 1.5            # retro carts/discs appreciate, esp. complete-in-box
        elif year < 1985:
            factor *= 1.6
        elif year < 2000:
            factor *= 1.25
        elif year >= 2015 and not is_game:
            factor *= 0.8            # new-ish discs/books are cheap; games hold value better
    # Well-loved titles hold value a bit better.
    if rating and rating >= 7.5:
        factor *= 1.2

    low = round(base * factor * 0.6, 0)
    high = round(base * factor * 1.8, 0)
    mid = round(base * factor, 0)

    out = {
        "currency": "USD" if tld in ("com", "ca", "com.au") else "local",
        "low": low,
        "mid": mid,
        "high": high,
        "display": f"~${int(mid)} ({int(low)}–{int(high)})",
        "sold_listings_url": _ebay_sold_url(title, year, fmt, tld),
        "note": "heuristic estimate — click to see real recent sold prices",
    }
    # Games: PriceCharting is the standard used-price reference (loose / CIB / sealed, by console).
    if is_game:
        out["price_check_url"] = _pricecharting_url(title, fmt)
        out["price_check_label"] = "PriceCharting"
    return out


def discogs_price(release_id: str, condition: str = "Very Good Plus (VG+)",
                  token: str | None = None) -> dict | None:
    """A condition-specific resale estimate for a music release from the Discogs marketplace.

    Token-gated (Discogs only serves price suggestions to authenticated users). Returns a resale
    dict shaped like `estimate()` (so callers can drop it in for music with a `discogs_release_id`)
    or None if unavailable. eBay remains the fallback for movies and tokenless setups."""
    from .metadata.discogs import DiscogsProvider
    info = DiscogsProvider(token=token).price_suggestion(str(release_id), condition)
    if not info or info.get("value") is None:
        return None
    val = round(float(info["value"]), 0)
    cur = info.get("currency") or "USD"
    return {
        "currency": cur, "low": round(val * 0.7, 0), "mid": val, "high": round(val * 1.4, 0),
        "display": f"~{int(val)} {cur} ({condition})",
        "discogs_release_id": str(release_id),
        "note": f"Discogs price suggestion ({condition})",
    }


def _pricecharting_url(title: str, platform: str | None = None) -> str:
    """A PriceCharting search link (the standard used-game price reference: loose / CIB / sealed)."""
    terms = title or ""
    if platform and platform not in ("Unknown", "PC"):
        terms += f" {platform}"
    return f"https://www.pricecharting.com/search-products?q={quote_plus(terms.strip())}&type=prices"


def _ebay_sold_url(title: str, year: int | None, fmt: str, tld: str) -> str:
    terms = title or ""
    if fmt and fmt != "Unknown":
        terms += f" {fmt}"
    q = quote_plus(terms.strip())
    return (f"https://www.ebay.{tld}/sch/i.html?_nkw={q}"
            f"&_sacat=0&LH_Sold=1&LH_Complete=1&rt=nc")
