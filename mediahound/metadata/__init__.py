"""Metadata providers: enrich an identified title with cover art + canonical fields."""
from __future__ import annotations

from .base import AudiobookMeta, BookMeta, GameMeta, MetadataProvider, MovieMeta, MusicMeta


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

    if media_type == "book":
        bcfg = (getattr(cfg, "data", {}) or {}).get("book", {}).get("metadata", {})
        name = (bcfg.get("provider") or "openlibrary").lower()
        if name == "openlibrary":
            from .openlibrary import OpenLibraryProvider
            return OpenLibraryProvider(bcfg)
        raise ValueError(f"Unknown book metadata provider: {name!r}")

    if media_type == "audiobook":
        acfg = (getattr(cfg, "data", {}) or {}).get("audiobook", {}).get("metadata", {})
        name = (acfg.get("provider") or "openlibrary").lower()
        if name in ("openlibrary", "librivox", "openlibrary+librivox"):
            from .audiobook import AudiobookProvider
            return AudiobookProvider(acfg)
        raise ValueError(f"Unknown audiobook metadata provider: {name!r}")

    if media_type == "game":
        gcfg = (getattr(cfg, "data", {}) or {}).get("game", {}).get("metadata", {})
        name = (gcfg.get("provider") or "wikidata").lower()
        if name in ("wikidata", "wikidata-games"):
            from .games import GameProvider
            return GameProvider(gcfg)
        raise ValueError(f"Unknown game metadata provider: {name!r}")

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


__all__ = ["MovieMeta", "MusicMeta", "BookMeta", "GameMeta", "AudiobookMeta",
           "MetadataProvider", "get_metadata_provider"]
