"""Metadata interface shared by every enrichment backend."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MovieMeta:
    matched: bool
    source: str = ""                 # "tmdb" | "wikidata" | "omdb"
    source_id: str = ""
    title: str | None = None
    original_title: str | None = None
    year: int | None = None
    category: str = "Film"           # Film | TV
    genres: list[str] = field(default_factory=list)
    language: str | None = None      # primary, human-readable (e.g. "English")
    spoken_languages: list[str] = field(default_factory=list)
    runtime: int | None = None       # minutes
    rating: float | None = None      # 0..10
    director: str | None = None
    actors: list[str] = field(default_factory=list)
    studio: str | None = None        # production company
    distributor: str | None = None
    tagline: str | None = None
    overview: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    source_url: str | None = None    # link back to TMDB/Wikipedia page
    raw: dict = field(default_factory=dict)


class MetadataProvider:
    name = "base"

    def lookup(self, title: str, year: int | None = None) -> MovieMeta:
        raise NotImplementedError
