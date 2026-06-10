"""Default, zero-key metadata provider: Wikipedia + Wikidata + Wikimedia Commons.

All open data — Wikidata is CC0, Wikipedia text is CC BY-SA, images via Wikimedia Commons.
No account or API key required.
"""
from __future__ import annotations

import time

import requests

from .base import MetadataProvider, MovieMeta

_WP = "https://en.wikipedia.org/w/api.php"
_WP_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_WD_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
_WD_API = "https://www.wikidata.org/w/api.php"
_COMMONS_FILE = "https://commons.wikimedia.org/wiki/Special:FilePath/{}?width=500"

_FILM_QIDS = {"Q11424", "Q24862", "Q229390", "Q506240", "Q202866"}  # film / short / TV film / anim
_TV_QIDS = {"Q5398426", "Q1259759", "Q581714"}                       # tv series / miniseries

_HEADERS = {"User-Agent": "ReelShelf/0.1 (open-source movie catalog; +https://github.com/)"}


class WikidataProvider(MetadataProvider):
    name = "wikidata"

    def __init__(self, cfg: dict):
        self.s = requests.Session()
        self.s.headers.update(_HEADERS)
        self.delay = float(cfg.get("delay", 0.4))  # be polite — Wikimedia rate-limits bots

    def _get(self, url, **params):
        """GET with one retry on 429, honoring a small inter-request delay."""
        for attempt in range(2):
            r = self.s.get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        return {}

    # -- helpers -----------------------------------------------------------
    def _search_page(self, title: str, year: int | None) -> str | None:
        data = self._get(_WP, action="query", list="search",
                         srsearch=f"{title} film", srlimit=5, format="json")
        hits = data.get("query", {}).get("search", [])
        return hits[0]["title"] if hits else None

    def _qid_for_page(self, page: str) -> str | None:
        data = self._get(_WP, action="query", prop="pageprops",
                         titles=page, format="json", redirects=1)
        pages = data.get("query", {}).get("pages", {})
        for p in pages.values():
            qid = p.get("pageprops", {}).get("wikibase_item")
            if qid:
                return qid
        return None

    def _labels(self, qids: list[str]) -> dict[str, str]:
        qids = [q for q in qids if q]
        if not qids:
            return {}
        out: dict[str, str] = {}
        for i in range(0, len(qids), 50):
            batch = qids[i:i + 50]
            ents = self._get(_WD_API, action="wbgetentities", ids="|".join(batch),
                             props="labels", languages="en", format="json").get("entities", {})
            for qid, ent in ents.items():
                lbl = ent.get("labels", {}).get("en", {}).get("value")
                if lbl:
                    out[qid] = lbl
        return out

    def _summary(self, page: str) -> dict:
        try:
            r = self.s.get(_WP_SUMMARY + page.replace(" ", "_"), timeout=30)
            if r.ok:
                return r.json()
        except requests.RequestException:
            pass
        return {}

    # -- main --------------------------------------------------------------
    def lookup(self, title: str, year: int | None = None) -> MovieMeta:
        if not title:
            return MovieMeta(False)
        if self.delay:
            time.sleep(self.delay)
        try:
            return self._lookup(title, year)
        except requests.RequestException:
            return MovieMeta(False)  # throttled / network → keep item as a manual entry

    def _lookup(self, title: str, year: int | None) -> MovieMeta:
        page = self._search_page(title, year)
        if not page:
            return MovieMeta(False)
        qid = self._qid_for_page(page)
        summary = self._summary(page)
        overview = summary.get("extract") or None
        thumb = (summary.get("thumbnail") or {}).get("source")
        source_url = (summary.get("content_urls", {}).get("desktop", {}).get("page")
                      or f"https://en.wikipedia.org/wiki/{page.replace(' ', '_')}")

        if not qid:
            # Still return a (weak) match from the Wikipedia summary alone.
            return MovieMeta(
                matched=True, source="wikipedia", source_id=page, title=page.split(" (")[0],
                year=year, overview=overview, poster_url=thumb, source_url=source_url,
            )

        ent = self._get(_WD_ENTITY.format(qid))
        claims = ent.get("entities", {}).get(qid, {}).get("claims", {})

        def qids_of(prop):
            vals = []
            for c in claims.get(prop, []):
                dv = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                if isinstance(dv, dict) and "id" in dv:
                    vals.append(dv["id"])
            return vals

        instance_of = set(qids_of("P31"))
        category = "TV" if instance_of & _TV_QIDS else "Film"
        genre_qids = qids_of("P136")
        lang_qids = qids_of("P364") or qids_of("P407")
        director_qids = qids_of("P57")[:2]
        cast_qids = qids_of("P161")[:5]
        studio_qids = qids_of("P272")[:2]      # production company
        distributor_qids = qids_of("P750")[:1]  # distributor

        # publication date -> year
        wd_year = year
        for c in claims.get("P577", []):
            t = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time")
            if t and len(t) >= 5:
                try:
                    y = int(t[1:5])
                    wd_year = y if wd_year is None else min(wd_year, y)
                except ValueError:
                    pass

        # poster image (P18) on Commons
        poster = thumb
        for c in claims.get("P18", []):
            fname = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if fname:
                poster = _COMMONS_FILE.format(fname.replace(" ", "_"))
                break

        labels = self._labels(genre_qids + lang_qids + director_qids + cast_qids
                              + studio_qids + distributor_qids)
        genres = [labels[q].replace(" film", "").strip().title()
                  for q in genre_qids if q in labels]
        languages = [labels[q] for q in lang_qids if q in labels]
        directors = [labels[q] for q in director_qids if q in labels]
        cast = [labels[q] for q in cast_qids if q in labels]
        studios = [labels[q] for q in studio_qids if q in labels]
        distributors = [labels[q] for q in distributor_qids if q in labels]

        return MovieMeta(
            matched=True,
            source="wikidata",
            source_id=qid,
            title=ent_label(ent, qid) or page.split(" (")[0],
            year=wd_year,
            category=category,
            genres=genres,
            language=languages[0] if languages else None,
            spoken_languages=languages,
            director=directors[0] if directors else None,
            actors=cast,
            studio=studios[0] if studios else None,
            distributor=distributors[0] if distributors else None,
            overview=overview,
            poster_url=poster,
            source_url=source_url,
            raw={"qid": qid, "page": page},
        )


def ent_label(ent: dict, qid: str) -> str | None:
    return ent.get("entities", {}).get(qid, {}).get("labels", {}).get("en", {}).get("value")
