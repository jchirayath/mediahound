# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

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

[0.1.0]: https://github.com/jchirayath/mediahound/releases/tag/v0.1.0
