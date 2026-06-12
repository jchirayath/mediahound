# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — 🖨 Printable inventory (PDF)
- `mediahound export --format inventory` writes a clean, self-contained `inventory.html` — grouped by
  media type with a per-type and grand-total estimated value — that prints (or **Save as PDF**) for
  insurance / offline sharing. Zero dependencies (the browser makes the PDF). The admin **⤓ Export**
  menu gains a one-click **🖨 Printable inventory (PDF)** button that builds the same page client-side
  (works on a static copy too). New `mediahound/inventory.py`.

## [0.6.0] — 2026-06-12

### Added — 🎧 Audiobooks (new media type)
- A fifth media type via the shared registry. Audiobooks resolve their book metadata
  (author/year/publisher/ISBN/cover) from **Open Library** and their audio bits (total **duration** +
  overview) from the **LibriVox** public catalogue — both **no API key**; narrator comes from the
  cover/CSV/manual. New `metadata/audiobook.py` (`AudiobookMeta`), a `🎧 Audiobooks` tab + card
  (duration "Xh Ym", narrator chip) + inline editor, `RawImages/audiobooks/`, CSV columns
  (`narrator`, `duration`), where-to-listen links (Audible / Libro.fm / LibriVox / Open Library), the
  Audible/CD/MP3-CD/Cassette/Digital medium dimension, `[audiobook.metadata]` config, and demo data.

### Added — 🎵 Album track-info & song search
- Each music card now shows a collapsible **tracklist**. Search already matched song titles; now when
  a query hits a track the album's tracklist **auto-opens** with the matched song highlighted — so you
  can find an album by any track on it. CSV round-trips tracklists (added to the export columns).

### Added — 🎮 Game resale (PriceCharting)
- Platform-aware used-value baselines (Switch / PS5 / PS4 / Xbox / PC / Retro — retro and Switch hold
  value; retro pre-2000 appreciates) and a **PriceCharting** price-check link (loose / CIB / sealed)
  alongside the eBay sold-listings link.

### Changed
- **Real demo cover art** for every media type (hotlinked, no copyrighted files stored): books &
  audiobooks via Open Library covers, games via Steam capsules (demo games are now The Witcher 3,
  Hades, Stardew Valley so each has real box art).
- CI: `softprops/action-gh-release` v2 → v3 (Node 24; clears the Node 20 deprecation warning).

## [0.5.0] — 2026-06-12

### Added — 📚 Books (new media type)
- A third media type alongside movies & music. Books resolve by **ISBN** (an EAN-13 with the 978/979
  prefix auto-routes as a book) or by title + author via **[Open Library](https://openlibrary.org)** —
  **no API key**. New `metadata/openlibrary.py` (`BookMeta`), book fields (author, publisher, year,
  pages, ISBN, subjects), a `📚 Books` tab, book card layout (author / publisher / pages / where-to-find
  links), a book inline editor, `RawImages/books/`, CSV import/export columns, `[book.metadata]` config,
  and `_MOCK_BOOKS` demo data. The movie/music field-clearing on a type-move generalised to N types.
  See [docs/design/05-new-media-types.md](docs/design/05-new-media-types.md).

### Added — 🎮 Video games (new media type)
- A fourth media type. Games resolve **by title** (or a scanned UPC → product name) via the
  **Wikidata Query Service** (SPARQL, P31 = video game) — open data, CC0, **no API key**. New
  `metadata/games.py` (`GameMeta`); **platform is the `format` dimension** (Switch / PS5 / PS4 / Xbox /
  PC / Retro, normalised from Wikidata platform labels); where-to-play links (`links.play_links`) that
  pick the storefront by platform (eShop / PS Store / Xbox / Steam + MobyGames). A `🎮 Games` tab, game
  card + inline editor (developer / publisher / platforms), `RawImages/games/`, CSV columns
  (`developer`, `platforms`), `[game.metadata]` config, UPC scan routing, and `_MOCK_GAMES`. The SPARQL
  title is escaped (no query injection). See [docs/design/05](docs/design/05-new-media-types.md).

### Added — 🧾 Compact change log
- `data/events.jsonl` — an append-only audit of every **add / remove / change**, tuned for size:
  integer unix-second timestamp, single-character op (`+ - ~ s l i`), and a *change* records only the
  **names** of the fields that changed (smallest record, and personal notes/ratings are never copied
  into a second file). Self-trims to a cap; **excluded from publish** (admin/audit only). View it with
  the new `mediahound log` command. See [`mediahound/events.py`](mediahound/events.py) and PRIVACY.md.

### Changed — shared media-type registry (internal)
- New media types are now added via a shared registry instead of copy-pasted branches: a frontend
  `TYPES` map drives the card meta/people/studio/where-to-X rows, a backend `_finalize_media` tail is
  shared across music/book/game, and the type-move field-clearing preserves fields the destination type
  also uses (e.g. `publisher` across book ↔ game). No new API keys (games stay zero-key by default).

## [0.4.0] — 2026-06-12

### Changed
- **New brand** — a beagle in headphones inside a retro **TV over an open book**, with the
  **media**(orange) **hound**(ink) wordmark. New icon everywhere (web favicon/apple-touch, macOS
  `.icns`, Windows `.ico`, README, wiki), brand palette (orange `#E97B0C` + ink `#16232A`) as the UI
  accent, and **Fredoka** as the brand/heading font. See [docs/brand/](docs/brand/).
- **Decluttered UI** — a two-row **sticky header** (brand/Help/Admin on top; media tabs + stats +
  Settings + Library below) that stays locked while scrolling, and the admin actions consolidated into
  popup menus: **➕ Add** (photos/scan/CSV), **🔗 Connect** (Discogs/Publish/Letterboxd),
  **⤓ Export** (catalog CSV/JSON, changes, seen), **💾 Backup** (backup/restore). Action rows wrap on
  narrow screens.
- **Inline Help** panel (❓) with searchable, collapsible sections; **Settings** dialog now scrolls and
  exposes the **Library & data folder** control.
- Desktop app slimmed **370 MB → 45 MB** by using the native macOS **WebKit** backend (excluded Qt +
  unused scientific libs in the PyInstaller spec); the bundle version is stamped from the package.

### Added — installable on your phone
- **📱 PWA** — published catalogs are now an installable, offline Progressive Web App (`manifest.json`
  + a service worker). Add it to your phone's home screen for a full-screen, offline-capable app that
  **auto-updates** on every republish (the SW cache is stamped with the build content-version).

### Added — the four design proposals ([docs/design/](docs/design/))
- **📷 Barcode / UPC scanning** — identify the *exact* release from the barcode instead of fuzzy OCR.
  Local decode via the optional `mediahound[barcode]` extra (`zxing-cpp`, a pip wheel, no system lib);
  music UPC → MusicBrainz/Discogs barcode search, movie UPC → UPCItemDB product name → the existing
  identify-by-title path. New `📷 Scan barcode` admin tool (native `BarcodeDetector` camera + manual
  entry), `POST /api/identify-barcode`, and a barcode-first pass in `mediahound build --online`.
- **💿 Discogs integration** — a Discogs music metadata provider (`[music.metadata] provider = "discogs"`),
  one-shot **collection import** (`mediahound import-discogs <username>`, a `💿 Discogs` button, and
  `POST /api/import-discogs`), and condition-based **price suggestions** (`resale.discogs_price`).
  Token stored in the OS keychain (`DISCOGS_TOKEN`, in Settings → API keys).
- **🛟 Interop & safety** — `mediahound backup` / `restore` (zip of RawImages + data + config; `--no-photos`
  for a quick curation-only backup; `.env`/secrets never included), a `⬇ Backup` button + `GET /api/backup`,
  **Letterboxd** and **JSON** exporters (`mediahound export --format letterboxd|json`, plus a client-side
  `🎬 Letterboxd` button), and **JSON Feed + RSS** of recently-added items (`data/feed.json` / `feed.xml`,
  `[feeds]` config).
- **⭐ Personal catalog** — per-item **rating** (★1–10), **note**, **tags/shelves**, and a **lending tracker**
  (loan out / returned, badge, On-loan filter), plus a **🎲 Surprise me** picker and a *My rating* sort.
  All personal data is **admin-only and stripped from the published catalog** (`bundle.js`/`collection.json`),
  and `corrections.json` / `loans.json` are excluded from Publish. See [PRIVACY.md](PRIVACY.md).
- **📚 Library switcher** — open / create / **switch the served library at runtime** from the admin UI,
  with no restart. Backed by a recents list (`~/.config/mediahound/recent.json`); `GET /api/libraries`,
  `POST /api/switch-library`, `POST /api/create-library` (all localhost-only). This is where the **data
  directory is chosen** — per library via `config.toml` `[paths]` — surfaced in the UI.

### Fixed
- **Upgrades now take effect** — an existing library kept its own copy of the web UI, so upgrading
  MediaHound left the old interface in place. `build`/app-open now refreshes the app shell from the
  installed package (`sync_web_assets`), and the server sends `no-cache` on HTML/JS/CSS so a webview
  can't run stale code.
- **`hidden` always wins** — a class that set `display` (e.g. the static-copy banner) overrode the
  HTML `hidden` attribute, so JS couldn't hide it. Added a global `[hidden] { display: none !important }`.
- **Static-copy guard** — editing a static copy (no admin server) now shows a clear banner that changes
  live only in that browser, with one-click Export.
- **Unidentified thumbnails** — the mock/demo build generates real placeholder tiles, and `identify.js`
  falls back gracefully when a thumbnail file is missing (no more blank/broken images).
- CI: green again (fixed Ruff lint in test helpers) and GitHub Actions bumped to Node-24 majors.

## [0.3.1] — 2026-06-11

### Fixed
- **Desktop app crashed on launch** ("started and exited"). PyInstaller ran `desktop.py` as
  `__main__`, which broke its package-relative imports (`from .config import …`). A launcher
  (`packaging/mediahound_app.py`) now imports the package so the app opens correctly. The macOS
  download is signed, **notarized**, and verified to launch.

### Added
- **New logo** — a hound **wearing headphones, watching TV** (music + movies, with the play-button
  nose). Full set: SVG icon + light/dark wordmark lockups, web favicon, and macOS `.icns` / Windows
  `.ico` app icons wired into the build. Brand kit + palette in [docs/brand/](docs/brand/).
- **Code-signing** — macOS Developer ID + notarization via **Fastlane** (`fastlane/Fastfile`; App
  Store Connect API key or app-specific password), and **free Windows signing via SignPath Foundation**
  for this open-source project. Both self-skip until configured. See [SIGNING.md](SIGNING.md).
- **[PRIVACY.md](PRIVACY.md)** — offline-first, no account or telemetry; a clear table of the only
  times data leaves your computer.

## [0.3.0] — 2026-06-11 — "Easy mode"

### Added — easier for non-technical users
- **🌐 One-click Publish** — a Publish button in the admin console deploys your catalog to **Netlify**
  (free hosting) and hands back a shareable link. Paste a Netlify access token once (saved in the OS
  keychain); the site id is remembered so the URL stays stable. Only the generated site is uploaded —
  `RawImages/`, `.env`, `config.toml` and dotfiles are never sent. Localhost-only (uses your token).
  New `mediahound/publish.py` + `POST /api/publish`.
- **`mediahound app`** — one command that sets up a library (if needed) and opens the editor in the
  browser. No config files, no separate `build`/`serve` steps to remember.
- **➕ Add photos (admin screen)** — **drag-and-drop** cover photos straight into the catalog
  (`POST /api/upload`): each photo is validated (must be a real image), filename-sanitised, saved into
  `RawImages/video` or `RawImages/audio`, and catalogued on rebuild. Localhost-only, same-origin-guarded.
- **First-run welcome screen** — an empty catalog now shows a friendly “add your first photos” card
  instead of a blank grid.
- **`mediahound app --phone`** — add photos **from your phone**: opens the editor to your local
  network and prints a **QR code** to scan. Capture is the same Add-photos flow (mobile browsers offer
  “Take Photo / Photo Library”). Uploads are **token-gated** — a secret baked into the QR link is
  required on every write — so only the device that scanned can edit; nothing leaves your network.
  Adds a small `qrcode` dependency.
- **Desktop app** — `mediahound gui` opens the editor in a **native window** (`pywebview`, with a
  browser fallback). A PyInstaller spec + `packaging/build-desktop.sh` + a `desktop.yml` workflow build
  a **double-clickable macOS `.app` / Windows `.exe`** (attached to releases), so non-technical users
  never touch Python or a terminal. The app keeps its library in `~/MediaHound Library`.
- **API keys in the admin console** — set TMDB / OMDb / Anthropic keys under **Settings → API keys**
  instead of editing a `.env`. Keys are stored in the **OS keychain** (`keyring`), never in a file and
  never returned to the browser (the UI shows only “✓ set / not set”). The build reads them via
  `keystore.load_into_env()` (real env and `.env` keep precedence). The set endpoint is
  **localhost-only — refused over the phone/LAN mode** even with a valid token. Adds a `keyring`
  dependency; new `mediahound/keystore.py`.

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

[0.3.1]: https://github.com/jchirayath/mediahound/releases/tag/v0.3.1
[0.3.0]: https://github.com/jchirayath/mediahound/releases/tag/v0.3.0
[0.2.0]: https://github.com/jchirayath/mediahound/releases/tag/v0.2.0
[0.1.0]: https://github.com/jchirayath/mediahound/releases/tag/v0.1.0
