"""Where-to-watch lookup via JustWatch's public GraphQL API (no key required).

Returns, for a title, which of the target streaming services carry it (with a direct
deep link and whether it's subscription / free / rent / buy), or none. JustWatch is the
data source behind most "where to watch" widgets; this is best-effort and region-specific.
"""
from __future__ import annotations

import requests

_API = "https://apis.justwatch.com/graphql"
_HEADERS = {"content-type": "application/json", "user-agent": "Mozilla/5.0 ReelShelf/0.1"}

# Default services to report on (display name -> JustWatch clearName match).
DEFAULT_TARGETS = {
    "Netflix": ("Netflix",),
    "Amazon Prime Video": ("Amazon Prime Video",),
    "Hulu": ("Hulu",),
}

# Best-offer ranking: subscription > free-with-ads > rent > buy.
_RANK = {"FLATRATE": 0, "FREE": 1, "ADS": 1, "RENT": 2, "BUY": 3, "CINEMA": 4}
_TYPE_LABEL = {"FLATRATE": "Stream", "FREE": "Free", "ADS": "Free (ads)",
               "RENT": "Rent", "BUY": "Buy", "CINEMA": "Cinema"}

_QUERY = """
query($f:String!,$c:Country!,$l:Language!){
  popularTitles(country:$c,first:1,filter:{searchQuery:$f}){
    edges{node{... on MovieOrShow{
      objectType
      content(country:$c,language:$l){title originalReleaseYear}
      offers(country:$c,platform:WEB){
        monetizationType
        package{clearName}
        standardWebURL
      }
    }}}
  }
}"""


def fetch_offers(title: str, year: int | None = None, country: str = "US",
                 targets: dict | None = None, session: requests.Session | None = None) -> dict:
    """Return {checked, providers:[{name,type,type_label,url}], justwatch_url}."""
    targets = targets or DEFAULT_TARGETS
    jw_search = f"https://www.justwatch.com/{country.lower()}/search?q={requests.utils.quote(title)}"
    result = {"checked": False, "providers": [], "justwatch_url": jw_search}
    if not title:
        return result
    s = session or requests
    try:
        r = s.post(_API, headers=_HEADERS, timeout=20, json={
            "query": _QUERY,
            "variables": {"f": title, "c": country, "l": "en"},
        })
        r.raise_for_status()
        edges = (r.json().get("data", {}).get("popularTitles", {}) or {}).get("edges", [])
    except (requests.RequestException, ValueError):
        return result  # checked stays False → UI can say "couldn't check"

    result["checked"] = True
    if not edges:
        return result
    node = edges[0].get("node", {})
    offers = node.get("offers", []) or []

    # best offer per target service
    best: dict[str, dict] = {}
    for off in offers:
        name = ((off.get("package") or {}).get("clearName") or "").strip()
        mon = off.get("monetizationType") or ""
        url = off.get("standardWebURL")
        if not name or not url:
            continue
        for display, aliases in targets.items():
            if name in aliases:
                rank = _RANK.get(mon, 9)
                if display not in best or rank < best[display]["_rank"]:
                    best[display] = {"name": display, "type": mon,
                                     "type_label": _TYPE_LABEL.get(mon, mon.title()),
                                     "url": url, "_rank": rank}
    result["providers"] = [
        {k: v for k, v in p.items() if k != "_rank"}
        for p in sorted(best.values(), key=lambda p: p["_rank"])
    ]
    return result
