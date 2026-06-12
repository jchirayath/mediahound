"""Metadata providers: enrich an identified title with cover art + canonical fields."""
from __future__ import annotations

from .base import MetadataProvider, MovieMeta, MusicMeta


def get_metadata_provider(cfg, media_type: str = "movie"):
    if media_type == "music":
        mcfg = (getattr(cfg, "data", {}) or {}).get("music", {}).get("metadata", {})
        name = (mcfg.get("provider") or "musicbrainz").lower()
        if name == "musicbrainz":
            from .musicbrainz import MusicBrainzProvider
            return MusicBrainzProvider(mcfg)
        if name == "discogs":
            from .discogs import DiscogsProvider
            return DiscogsProvider(mcfg)
        raise ValueError(f"Unknown music metadata provider: {name!r}")

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


__all__ = ["MovieMeta", "MusicMeta", "MetadataProvider", "get_metadata_provider"]
