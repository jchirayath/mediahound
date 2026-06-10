# MediaHound — design (multi-media evolution of ReelShelf)

Status: **accepted** · Supersedes the movie-only scope · Target: v0.2

MediaHound generalizes ReelShelf from a DVD/VHS movie catalog into a **multi-media** physical-
collection catalog covering **movies** (DVD/VHS/Blu-ray/LaserDisc) and **music** (CD/Vinyl/Cassette),
from photos of the covers **or** a CSV import, identified via public data sources, with where-to-watch
/ where-to-listen links.

## Why it's tractable

The pipeline spine is already media-agnostic: incremental sha256 manifest, offline-first build,
static-site output, the cover-download + cache infra, admin round-trip JSON, and — crucially — the
**provider factory pattern** (`get_identifier` / `get_metadata_provider` are clean `name → class`
switches). Only the *schema* and the *providers* are movie-coupled. So MediaHound is an **additive
`media_type` axis**, not a rewrite.

## Core data model — one `MediaItem`, discriminated by `media_type`

```jsonc
MediaItem {
  "id", "media_type": "movie" | "music",
  "title", "year", "format",        // DVD/VHS/Blu-ray/LaserDisc | CD/Vinyl/Cassette
  "creators": [{"role","name"}],     // director/cast | artist/composer
  "label", "genres": [...], "rating",
  "cover_images": [...], "intro",
  "value": {low,mid,high,sold_url},
  "links": { "watch": [...], "listen": [...] },
  "status": {"consumed": bool, "date": "..."},
  "details": { /* movie: runtime,language · music: tracklist[],discs,duration,catalog_no,barcode */ },
  "source", "source_url"
}
```

Implemented as a `MediaMeta` base with `MovieMeta` / `MusicMeta` subclasses. `media_type` = content
domain; `format` = physical carrier. (LaserDisc is video → `media_type: movie`.)

## Providers — add a media-type axis

`get_metadata_provider(cfg, media_type)`, `get_identifier(cfg, media_type)`,
`get_links_provider(...)`, `get_resale_provider(...)`.

| Capability | Zero-key default | Premium (free key) |
|---|---|---|
| Music metadata | **MusicBrainz** (CC0, no key) | **Discogs** (format/label/catalog#/pressing) |
| Music cover art | **Cover Art Archive** | Discogs images |
| Where-to-listen | keyless search deep-links (Spotify / Apple Music / YouTube Music) | Spotify / Apple MusicKit exact links |
| Music resale | eBay sold listings | **Discogs price suggestions** |

Movie providers (TMDB/OMDb/Wikidata, JustWatch, eBay) are unchanged.

## Identifying movie vs music from a photo

1. **Aspect-ratio heuristic** — album art ≈ square; movie covers ≈ 2:3.
2. **Folder / `--type` hint** — `RawImages/movies/`, `RawImages/music/`.
3. **Vision/OCR + barcode** (UPC/EAN → MusicBrainz/Discogs). Admin can override per item.

## CSV import/export (new)

`mediahound import catalog.csv` — rows become identifications that skip OCR and flow straight into
enrichment (covers from Cover Art Archive / TMDB). De-duped by barcode or `media_type|title|year|creator`.
`mediahound export` writes the whole catalog back to CSV (backup/migration).

## Frontend

A segmented **`All · 🎬 Movies · 🎵 Music`** control over the existing filter framework; cards render a
per-`media_type` field set (director/cast/studio/runtime + ▶ watch · artist/label/tracklist + ♫ listen);
filters become type-aware. The admin view-config becomes two field sets keyed by type.

## Phases

0. Rebrand reelshelf → mediahound (mechanical).
1. Generalize core (`media_type` + `MediaMeta`); movies keep working.
2. Music providers (MusicBrainz + Cover Art Archive → Discogs → listen links → price).
3. Routing + CSV import/export.
4. UI: media tab, per-type cards/fields, listen badges, mixed-media demo.
5. Polish: tests, docs, migration script for existing movie data.

## Risks / decisions

- One-time migration of existing movie catalogs (`media_type:"movie"`, `images`→`cover_images`,
  `seen`→`status`) with a back-compat reader.
- Apple Music exact links need a paid dev token → ship keyless search links by default.
- MusicBrainz 1 req/s rate limit → existing cache + backoff handles it.
