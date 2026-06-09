"""Metadata providers: enrich an identified title with poster + canonical fields."""
from __future__ import annotations

from .base import MovieMeta, MetadataProvider


def get_metadata_provider(cfg) -> MetadataProvider:
    name = cfg.metadata.get("provider", "wikidata").lower()
    if name == "wikidata":
        from .wikidata import WikidataProvider
        return WikidataProvider(cfg.metadata.get("wikidata", {}))
    if name == "tmdb":
        from .tmdb import TMDBProvider
        return TMDBProvider(cfg.metadata.get("tmdb", {}))
    if name == "omdb":
        from .omdb import OMDBProvider
        return OMDBProvider(cfg.metadata.get("omdb", {}))
    raise ValueError(f"Unknown metadata provider: {name!r}")


__all__ = ["MovieMeta", "MetadataProvider", "get_metadata_provider"]
