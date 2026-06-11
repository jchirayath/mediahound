# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — easier for non-technical users
- **`mediahound app`** — one command that sets up a library (if needed) and opens the editor in the
  browser. No config files, no separate `build`/`serve` steps to remember.
- **➕ Add photos (admin screen)** — **drag-and-drop** cover photos straight into the catalog
  (`POST /api/upload`): each photo is validated (must be a real image), filename-sanitised, saved into
  `RawImages/video` or `RawImages/audio`, and catalogued on rebuild. Localhost-only, same-origin-guarded.
- **First-run welcome screen** — an empty catalog now shows a friendly “add your first photos” card
  instead of a blank grid.

## [0.2.0] — 2026-06-11 — "MediaHound"

Renamed **ReelShelf → MediaHound** and grew from a movie catalog into a **multi-media** catalog
(movies *and* music).

### Added
- **Music support** — catalog CDs, vinyl and cassettes. New `media_type` discriminator and a
  `MusicMeta` model; **MusicBrainz + Cover Art Archive** metadata provider (open, zero-key); keyless
  **Spotify / Apple Music / YouTube Music** "where-to-listen" links.
- **Raw-image folder convention** — `RawImages/video/` → movies, `RawImages/audio/` → music; the
  build routes each photo to the right identify/enrich path by its subfolder, and `init` scaffolds both.
- **CSV import/export** — `mediahound import catalog.csv` bulk-adds movies & music (no photos
  needed), optionally enriched online; `mediahound export -o catalog.csv` backs up the catalog.
- **Frontend** — a **🎬 Movies / 🎵 Music** segmented filter, per-media-type cards (artist / label /
  tracklist / ♫ listen for music), and music-aware search.
- Provider factory now routes by media type: `get_metadata_provider(cfg, media_type)`.
- **`mediahound serve`** — preview the generated site over http (no more file:// fetch limits).
- **`mediahound serve --admin`** — a localhost-only write API so admin-portal edits save **straight
  into `data/corrections.json`** (and `seen-overrides.json`) as you make them. No "Export changes →
  drop file in" step; edits persist immediately and **survive every future build** (the long-standing
  cause of "my manual title fix reverted on rebuild"). Cross-origin writes are refused; a **↻ Rebuild**
  button re-bakes the catalog in place. See `mediahound/serve.py` and
  [docs/EDITING.md](docs/EDITING.md).
- **Move a title between Movies & Music from the admin screen** — the inline editor now has a
  🎬 Movie / 🎵 Music selector (with an Artist field and CD/Vinyl/Cassette formats for music).
  Switching type sets a `media_type` correction, clears the previous type's exclusive fields, and
  auto-ticks re-query so the next `--online` build re-enriches with the correct provider
  (movie ↔ music). New `_apply_meta_to_music()`; `_apply_corrections` is now media-type-aware.
  On the next build the move also **relocates the source cover photo** into the matching
  `RawImages/video` or `RawImages/audio` folder (idempotent, path-traversal-guarded), so a
  reclassified title is correct at the source and won't revert if `corrections.json` is cleared.
- **⬆ Import list (admin screen)** — under `serve --admin`, a new button + `POST /api/import` lets you
  paste or upload a CSV and bulk-add titles (optionally enriched online), with the site rebuilt in
  place. Same importer as the CLI: only `title` is required.

### Changed
- **Filters are now media-type-aware** — the Format / Genre / Studio·Label / Language dropdowns
  narrow to the active 🎬 Movies or 🎵 Music tab (and show everything under *All*), so you no longer
  see movie-only formats while browsing music.
- Rebrand across package, CLI (`mediahound`), JS data global, `localStorage` keys, branding and docs.
- Default site title/subtitle are media-generic.

### Fixed
- **“Export changes” now merges** with the site's existing `data/corrections.json` before downloading,
  so exporting can never silently drop a previously-saved correction (which would make that title
  revert on the next build).
- **Format is normalised when a title changes type** — a movie-only format left on a music item
  (e.g. a CD that was catalogued as a `DVD`) is reset to the new type's default, so the card's format
  badge and meta line no longer show `DVD` on music (or `CD` on a movie). Applied both in the build
  and live in the portal.

## [0.1.0] — 2026-06-09

First public release.

### Added
- **CLI** — `mediahound init <dir>` scaffolds a site; `mediahound build` turns a folder of cover
  photos into a static catalog. Incremental (only new photos are processed, tracked by sha256).
- **Offline-first** — builds never touch the network unless `--online` is passed.
- **Pluggable providers**
  - Identify: `tesseract` (default, zero-key OCR), `claude` (vision), `ollama` (local).
  - Metadata: `wikidata` (default, zero-key), `tmdb`, `omdb`.
  - Where-to-watch via JustWatch (no key); resale estimates with eBay sold-listings links.
- **Static web app** (vanilla JS, no build step)
  - Read-only **default view** + password-protected **admin view** (read/write).
  - Dense, aligned cards: poster, title·year, rating·format·runtime·language, genres, director +
    cast, studio, where-to-watch, intro hook, estimated resale value.
  - Clickable genre / person / studio filters; streaming-service filter; adjustable columns;
    responsive web + mobile.
  - Multi-photo galleries with ‹ › arrows, click-to-zoom, rotate, and set-default.
  - Admin: edit name/year/format/studio, mark seen, delete a title or a photo, manual
    identification (name or discard unidentified covers), and configure the library name, logo,
    description, shown fields, and default columns.
  - Edits round-trip through small JSON files (`corrections.json`, `seen-overrides.json`,
    `view-config.json`, `identify-queue.json`) applied on the next build.
  - Works from `file://` via an embedded `data/bundle.js`; content-hash cache-busting for updates.
- **Demo** — `--mock` builds a 10-title sample catalog (real posters hotlinked for illustration;
  no copyrighted images stored in the repo). Hosted live on GitHub Pages.
- **Robustness** — metadata caching, soft-failing providers, and a plausible-title guard that
  rejects fuzzy mismatches so they can't corrupt your data.
- **Docs & CI** — README, ARCHITECTURE, DEPLOYMENT (with free-hosting options), SECURITY,
  CONTRIBUTING; GitHub Actions CI (tests + mock build + `pip-audit`); Dependabot.

### Security
- All rendered data is HTML-escaped; links are restricted to `http(s)` / site-relative URLs.
- Photo-rotation corrections are guarded against path traversal; poster downloads are `http(s)`-only.
- Secrets live only in a gitignored `.env`; only the admin password **hash** is published. The admin
  gate is a convenience control, not server-side auth (see [SECURITY.md](SECURITY.md)).

[0.2.0]: https://github.com/jchirayath/mediahound/releases/tag/v0.2.0
[0.1.0]: https://github.com/jchirayath/mediahound/releases/tag/v0.1.0
