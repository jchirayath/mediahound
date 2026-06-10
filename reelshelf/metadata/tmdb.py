"""TMDB metadata provider (best posters/metadata). Free API key required.

Set TMDB_API_KEY in the instance .env (gitignored) or environment.
Data and images courtesy of The Movie Database (https://www.themoviedb.org); not endorsed by TMDB.
"""
from __future__ import annotations

import os

import requests

from .base import MetadataProvider, MovieMeta

_BASE = "https://api.themoviedb.org/3"
_IMG = "https://image.tmdb.org/t/p"

# ISO-639-1 -> human readable (common cases; falls back to the code)
_LANG = {
    "en": "English", "fr": "French", "es": "Spanish", "de": "German", "it": "Italian",
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "hi": "Hindi", "ru": "Russian",
    "pt": "Portuguese", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam", "ar": "Arabic",
    "sv": "Swedish", "nl": "Dutch", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
    "pl": "Polish", "tr": "Turkish", "th": "Thai", "cn": "Chinese",
}


class TMDBProvider(MetadataProvider):
    name = "tmdb"

    def __init__(self, cfg: dict):
        self.language = cfg.get("language", "en-US")
        self.api_key = os.environ.get("TMDB_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "TMDB_API_KEY is not set. Get a free key at "
                "https://www.themoviedb.org/settings/api and add it to .env (gitignored)."
            )

    def _get(self, path: str, **params) -> dict:
        params["api_key"] = self.api_key
        params.setdefault("language", self.language)
        r = requests.get(f"{_BASE}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def lookup(self, title: str, year: int | None = None) -> MovieMeta:
        if not title:
            return MovieMeta(False)
        params = {"query": title}
        if year:
            params["year"] = year
        results = self._get("/search/movie", **params).get("results", [])
        if not results and year:
            results = self._get("/search/movie", query=title).get("results", [])
        if not results:
            return MovieMeta(False)

        hit = results[0]
        mid = hit["id"]
        d = self._get(f"/movie/{mid}", append_to_response="credits")
        credits = d.get("credits", {})
        actors = [c["name"] for c in credits.get("cast", [])[:5] if c.get("name")]
        director = next((c["name"] for c in credits.get("crew", [])
                         if c.get("job") == "Director"), None)
        companies = [c["name"] for c in d.get("production_companies", []) if c.get("name")]
        lang_code = d.get("original_language") or ""
        spoken = [
            _LANG.get(sl.get("iso_639_1", ""), sl.get("english_name") or sl.get("name", ""))
            for sl in d.get("spoken_languages", [])
        ]
        rel = d.get("release_date") or ""
        poster = d.get("poster_path")
        backdrop = d.get("backdrop_path")
        return MovieMeta(
            matched=True,
            source="tmdb",
            source_id=str(mid),
            title=d.get("title") or title,
            original_title=d.get("original_title"),
            year=int(rel[:4]) if rel[:4].isdigit() else year,
            category="Film",
            genres=[g["name"] for g in d.get("genres", [])],
            language=_LANG.get(lang_code, lang_code.upper() or None),
            spoken_languages=[s for s in spoken if s],
            runtime=d.get("runtime") or None,
            rating=round(d["vote_average"], 1) if d.get("vote_average") else None,
            director=director,
            actors=actors,
            studio=companies[0] if companies else None,
            tagline=(d.get("tagline") or None),
            overview=(d.get("overview") or None),
            poster_url=f"{_IMG}/w500{poster}" if poster else None,
            backdrop_url=f"{_IMG}/w1280{backdrop}" if backdrop else None,
            source_url=f"https://www.themoviedb.org/movie/{mid}",
            raw={"id": mid},
        )
