"""Metadata interface shared by every enrichment backend."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MovieMeta:
    matched: bool
    media_type: str = "movie"
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


@dataclass
class MusicMeta:
    """Enrichment result for a music release (album/single on CD, vinyl, cassette)."""
    matched: bool
    media_type: str = "music"
    source: str = ""                 # "musicbrainz" | "discogs"
    source_id: str = ""
    title: str | None = None         # release / album title
    artist: str | None = None
    year: int | None = None
    genres: list[str] = field(default_factory=list)
    label: str | None = None         # record label
    catalog_no: str | None = None
    barcode: str | None = None
    format: str | None = None        # CD | Vinyl | Cassette
    disc_count: int | None = None
    tracklist: list[str] = field(default_factory=list)
    rating: float | None = None
    overview: str | None = None
    cover_url: str | None = None
    source_url: str | None = None    # link to MusicBrainz / Discogs page
    raw: dict = field(default_factory=dict)


@dataclass
class BookMeta:
    """Enrichment result for a book (by ISBN, or title + author)."""
    matched: bool
    media_type: str = "book"
    source: str = ""                 # "openlibrary" | "googlebooks"
    source_id: str = ""
    title: str | None = None
    author: str | None = None        # primary author(s), human-readable
    year: int | None = None          # first/publish year
    genres: list[str] = field(default_factory=list)   # subjects
    publisher: str | None = None
    isbn: str | None = None
    format: str | None = None        # Hardcover | Paperback | eBook | Audiobook
    page_count: int | None = None
    series: str | None = None
    rating: float | None = None      # 0..10 if available
    overview: str | None = None
    cover_url: str | None = None
    source_url: str | None = None    # link to the Open Library / Google Books page
    raw: dict = field(default_factory=dict)


@dataclass
class AudiobookMeta:
    """Enrichment result for an audiobook (book metadata + narrator/duration)."""
    matched: bool
    media_type: str = "audiobook"
    source: str = ""                 # "openlibrary" | "librivox" | "openlibrary+librivox"
    source_id: str = ""
    title: str | None = None
    author: str | None = None
    narrator: str | None = None      # the reader/voice (often only on the cover → OCR/manual/CSV)
    year: int | None = None
    genres: list[str] = field(default_factory=list)
    publisher: str | None = None     # audio publisher (Audible Studios, Brilliance, …)
    isbn: str | None = None
    format: str | None = None        # Audible | CD | MP3-CD | Cassette | Digital
    duration: int | None = None      # total length in minutes
    rating: float | None = None
    overview: str | None = None
    cover_url: str | None = None
    source_url: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class GameMeta:
    """Enrichment result for a video game (by title, or UPC → product name → title)."""
    matched: bool
    media_type: str = "game"
    source: str = ""                 # "wikidata" | "rawg" | "igdb"
    source_id: str = ""
    title: str | None = None
    developer: str | None = None     # the studio that made it
    publisher: str | None = None
    year: int | None = None
    genres: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    format: str | None = None        # primary platform (Switch | PS5 | Xbox | PC | Retro …)
    players: str | None = None       # e.g. "1-4"
    esrb: str | None = None
    rating: float | None = None      # 0..10 if available
    overview: str | None = None
    cover_url: str | None = None
    source_url: str | None = None    # link to the Wikidata / RAWG page
    raw: dict = field(default_factory=dict)


class MetadataProvider:
    name = "base"
    media_type = "movie"

    def lookup(self, title: str, year: int | None = None) -> MovieMeta:
        raise NotImplementedError
