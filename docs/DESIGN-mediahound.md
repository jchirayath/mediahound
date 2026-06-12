# MediaHound — design (multi-media evolution of MediaHound)

Status: **accepted** · Supersedes the movie-only scope · Target: v0.2

MediaHound generalizes MediaHound from a DVD/VHS movie catalog into a **multi-media** physical-
collection catalog. It started with **movies** (DVD/VHS/Blu-ray/LaserDisc) and **music** (CD/Vinyl/
Cassette) and now also covers **books**, **video games** (Switch/PS5/PS4/Xbox/PC/Retro) and
**audiobooks** (Audible/CD/MP3-CD/Cassette/Digital) — five media types in all — from photos of the
covers **or** a CSV import, identified via zero-key public data sources, with where-to-watch /
-listen / -play / -read links.

## Why it's tractable

The pipeline spine is already media-agnostic: incremental sha256 manifest, offline-first build,
static-site output, the cover-download + cache infra, admin round-trip JSON, and — crucially — the
**provider factory pattern** (`get_identifier` / `get_metadata_provider` are clean `name → class`
switches). Only the *schema* and the *providers* are movie-coupled. So MediaHound is an **additive
`media_type` axis**, not a rewrite.

## Core data model — one `MediaItem`, discriminated by `media_type`

```jsonc
MediaItem {
  "id", "media_type": "movie" | "music" | "book" | "game" | "audiobook",
  "title", "year", "format",        // DVD/VHS/Blu-ray | CD/Vinyl | book | platform (Switch/PS5/…) | medium
  "creators": [{"role","name"}],     // director/cast | artist | author | developer | author/narrator
  "label", "genres": [...], "rating",
  "cover_images": [...], "intro",
  "value": {low,mid,high,sold_url},
  "links": { "watch": [...], "listen": [...] },
  "status": {"consumed": bool, "date": "..."},
  "details": { /* movie: runtime,language · music: tracklist[],discs,duration,catalog_no,barcode */ },
  "source", "source_url"
}
```

Implemented as a `MediaMeta` base with `MovieMeta` / `MusicMeta` / `BookMeta` / `GameMeta` /
`AudiobookMeta` subclasses. `media_type` = content domain; `format` = physical carrier (for games it's
the **platform**, for audiobooks the **medium**). (LaserDisc is video → `media_type: movie`.) A shared
media-type **registry** (frontend `TYPES` map + backend `_finalize_media` tail) means adding a type is
~one registry entry + a provider, and moving an item between types preserves shared fields.

## Providers — add a media-type axis

`get_metadata_provider(cfg, media_type)`, `get_identifier(cfg, media_type)`,
`get_links_provider(...)`, `get_resale_provider(...)`.

| Capability | Zero-key default | Premium (free key) |
|---|---|---|
| Music metadata | **MusicBrainz** (CC0, no key) | **Discogs** (format/label/catalog#/pressing) — *shipped* |
| Music cover art | **Cover Art Archive** | Discogs images |
| Where-to-listen | keyless search deep-links (Spotify / Apple Music / YouTube Music) | Spotify / Apple MusicKit exact links |
| Music resale | eBay sold listings | **Discogs price suggestions** — *shipped* |
| Book / audiobook metadata | **Open Library** (author/cover/publisher/ISBN, no key) | — |
| Audiobook duration / overview | **LibriVox** (public-domain catalogue, no key) | — |
| Where-to-listen (audiobook) | Audible / Libro.fm / LibriVox / Open Library links | — |
| Game metadata | **Wikidata** query service (`P31`=video game; UPC→title; platform→`format`) | — |
| Where-to-play (game) | platform storefront (eShop / PS Store / Xbox / Steam) + MobyGames | — |
| Game resale | eBay sold listings + **PriceCharting** price-check link | — |

Movie providers (TMDB/OMDb/Wikidata, JustWatch, eBay) are unchanged. The book/game/audiobook
providers (`metadata/openlibrary.py`, `metadata/games.py`, `metadata/audiobook.py`) are all zero-key.

## Identifying movie vs music from a photo

1. **Aspect-ratio heuristic** — album art ≈ square; movie covers ≈ 2:3.
2. **Folder / `--type` hint** — `RawImages/movies/`, `RawImages/music/`.
3. **Vision/OCR + barcode** (UPC/EAN → MusicBrainz/Discogs). Admin can override per item.

## CSV import/export (new)

`mediahound import catalog.csv` — rows become identifications that skip OCR and flow straight into
enrichment (covers from Cover Art Archive / TMDB). De-duped by barcode or `media_type|title|year|creator`.
`mediahound export` writes the whole catalog back to CSV (backup/migration).

## Frontend

A segmented **`All · 🎬 Movies · 🎵 Music · 📚 Books · 🎮 Games · 🎧 Audiobooks`** control over the
existing filter framework; cards render a per-`media_type` field set (director/cast/studio/runtime +
▶ watch · artist/label/tracklist + ♫ listen · author/publisher/ISBN + 📖 read · developer/platform +
🎮 play · author/narrator/duration + 🎧 listen); filters become type-aware. Music cards show a
collapsible tracklist (under the artist) and a song search surfaces its album with the matched track
highlighted. The admin view-config becomes one field set per type, driven by the shared `TYPES`
registry. Per-card creator/label icons are an inline-SVG set (not OS-dependent emoji).

The grid is **virtualized** (paint a chunk, append more on scroll) so multi-thousand-item catalogs
stay responsive, with an **A–Z jump rail** for long title-sorted lists. Card spacing uses **container
queries** — alignment heights apply only in the dense grid, so wide / single-column cards flow
naturally. Below 640px the chrome goes mobile-first: filters behind a toggle, condensed header, ≥44px
tap targets, a two-column grid.

## Phases

0. Rebrand mediahound → mediahound (mechanical).
1. Generalize core (`media_type` + `MediaMeta`); movies keep working.
2. Music providers (MusicBrainz + Cover Art Archive → Discogs → listen links → price).
3. Routing + CSV import/export.
4. UI: media tab, per-type cards/fields, listen badges, mixed-media demo.
5. Polish: tests, docs, migration script for existing movie data.

> **Status (shipped, as of v0.7.0).** All phases landed and the type axis grew past movies + music to
> **five** types: books (Open Library), 🎮 video games (Wikidata; PriceCharting resale) and 🎧
> audiobooks (Open Library + LibriVox) were added via the shared media-type registry. Also shipped
> since: album track-info + song search, a compact change log (`events.jsonl`, `mediahound log`), a
> printable inventory PDF (`export --format inventory` / `inventory.py`), Discogs import + price
> suggestions, and real demo cover art for every type. **v0.7.0** added a virtualized grid + A–Z jump
> rail, container-query card layout, a mobile-first chrome pass, an inline-SVG icon set, a
> service-worker cache-bust fix, and `tools/` for bulk music-library import/cleanup/cover enrichment.

## Risks / decisions

- One-time migration of existing movie catalogs (`media_type:"movie"`, `images`→`cover_images`,
  `seen`→`status`) with a back-compat reader.
- Apple Music exact links need a paid dev token → ship keyless search links by default.
- MusicBrainz 1 req/s rate limit → existing cache + backoff handles it.
