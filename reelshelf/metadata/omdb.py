"""Optional OMDb metadata provider. Free API key required (http://www.omdbapi.com/apikey.aspx).

Set OMDB_API_KEY in the instance .env (gitignored) or environment.
"""
from __future__ import annotations

import os

import requests

from .base import MovieMeta, MetadataProvider

_BASE = "https://www.omdbapi.com/"


class OMDBProvider(MetadataProvider):
    name = "omdb"

    def __init__(self, cfg: dict):
        self.api_key = os.environ.get("OMDB_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OMDB_API_KEY is not set. Get a free key at "
                "http://www.omdbapi.com/apikey.aspx and add it to .env (gitignored)."
            )

    def lookup(self, title: str, year: int | None = None) -> MovieMeta:
        if not title:
            return MovieMeta(False)
        params = {"apikey": self.api_key, "t": title, "type": "movie"}
        if year:
            params["y"] = year
        try:
            r = requests.get(_BASE, params=params, timeout=30)
            r.raise_for_status()
            d = r.json()
        except (requests.RequestException, ValueError):
            return MovieMeta(False)  # network/quota issue → treat as "no match", never crash
        if d.get("Response") != "True":
            # e.g. {"Response":"False","Error":"Request limit reached!"} → no match (not fatal)
            return MovieMeta(False)
        rating = None
        try:
            rating = float(d.get("imdbRating")) if d.get("imdbRating", "N/A") != "N/A" else None
        except ValueError:
            pass
        runtime = None
        rt = (d.get("Runtime") or "").split()
        if rt and rt[0].isdigit():
            runtime = int(rt[0])
        poster = d.get("Poster")
        actors = [a.strip() for a in (d.get("Actors") or "").split(",")
                  if a.strip() and a.strip() != "N/A"]
        director = (d.get("Director") or "").strip()
        director = director if director and director != "N/A" else None
        studio = (d.get("Production") or "").strip()
        studio = studio if studio and studio != "N/A" else None
        return MovieMeta(
            matched=True,
            source="omdb",
            source_id=d.get("imdbID", ""),
            title=d.get("Title") or title,
            year=int(d["Year"][:4]) if d.get("Year", "")[:4].isdigit() else year,
            genres=[g.strip() for g in (d.get("Genre") or "").split(",") if g.strip()],
            language=(d.get("Language") or "").split(",")[0].strip() or None,
            spoken_languages=[l.strip() for l in (d.get("Language") or "").split(",") if l.strip()],
            runtime=runtime,
            rating=rating,
            director=director,
            actors=actors,
            studio=studio,
            overview=(d.get("Plot") or None),
            poster_url=poster if poster and poster != "N/A" else None,
            source_url=f"https://www.imdb.com/title/{d.get('imdbID')}/" if d.get("imdbID") else None,
            raw=d,
        )
