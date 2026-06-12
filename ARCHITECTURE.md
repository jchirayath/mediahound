# MediaHound — Architecture

MediaHound is two halves that meet at a folder of JSON files:

1. A **Python CLI** (`mediahound/`) that reads cover photos and writes a catalog.
2. A **static, dependency-free web app** (`mediahound/web/`) that renders that catalog.

They never talk at runtime — the CLI produces files; the site reads them.

```
┌─────────────────────────── mediahound build ───────────────────────────┐
│  RawImages/video/*.jpg → movie     RawImages/audio/*.jpg → music        │
│  (+ book / game / audiobook covers, by folder / type hint)              │
│      │  sha256 → data/manifest.json   (incremental: skip already-done)  │
│      ▼                                                                   │
│  identify  ──────────────►  Identification(title, year, format, …)      │
│  (tesseract | claude | ollama)                                          │
│      │  confidence ≥ threshold?  no → data/unidentified.json            │
│      ▼  route by media_type  →  _finalize_media (shared per-type tail)  │
│   ┌────────┴────────┬──────────┬──────────┬──────────────┐              │
│   ▼ movie            ▼ music    ▼ book      ▼ game         ▼ audiobook   │
│  wikidata|tmdb|omdb  musicbrainz openlibrary wikidata      openlibrary  │
│  + Cover Art Archive +CoverArtArc (P31=game) +librivox                  │
│  MovieMeta           MusicMeta   BookMeta   GameMeta       AudiobookMeta │
│   │  + plausible-title guard / shared-field preservation on type moves  │
│   └──────────────────────────┬──────────────────────────────┘          │
│      ▼  intro (hook) + resale(eBay / Discogs / PriceCharting) + links   │
│  data/collection.json   posters/   originals/   data/bundle.js          │
│  data/events.jsonl  (append-only audit; excluded from publish)          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
   web/index.html + assets/js/app.js  (🎬 / 🎵 / 📚 / 🎮 / 🎧 type tabs, TYPES registry)
```

## Python package (`mediahound/`)

| Module | Responsibility |
|---|---|
| `cli.py` | Subcommands (argparse): `init`, `build`, `import`, `export` (incl. `--format inventory`), `serve`, **`app`** (the one-command easy path), **`gui`** (native desktop window), **`log`** (view the change log). |
| `config.py` | Loads `config.toml`, merges defaults, loads `.env` secrets **then fills any unset key from the OS keychain** (`keystore.load_into_env()`), resolves paths. |
| `pipeline.py` | Orchestration: scan → identify → enrich → intro/resale/streaming → write. Also `--mock`, corrections, offline/online gating, and the metadata cache + plausibility guard. The shared **`_finalize_media`** helper is the common per-type tail (cover, resale, links, write), so each media type is a thin enrich function, not a duplicated branch. **`stamp_cache_bust`** stamps a content version (a hash of the data bundle **plus** `app.js`/`styles.css`) onto the HTML asset URLs and the service-worker cache name, so any rebuild — data **or** UI — invalidates stale browser/SW caches. |
| `store.py` | The incremental `manifest.json` and the JSON the website reads (collection / unidentified). Merges duplicate photos into one gallery; applies seen/corrections. |
| `imaging.py` | Pillow helpers: prepare a compact JPEG for OCR/vision, save thumbnails, auto-upright landscape covers, rotate, placeholder posters for `--mock`. |
| `serve.py` | `serve` previews the site; on start it refreshes the app shell from the installed package (`sync_web_assets`) **then re-applies `stamp_cache_bust`** so the service worker doesn't pin to the template's un-stamped version. `serve --admin` exposes a **localhost-only write API** so admin edits save straight to `data/` (+ photo upload, CSV import, rebuild, API-keys, publish). `--phone` binds to the LAN with a **per-session token + QR** for uploading from a phone. |
| `desktop.py` | The desktop app: sets up `~/MediaHound Library`, starts the admin server, opens it in a **native webview window** (browser fallback). PyInstaller entry point for the `.app`/`.exe`. |
| `keystore.py` | Provider/publish secrets in the **OS keychain** (`keyring`): TMDB/OMDb/Anthropic + the Netlify token. Write-only from the UI; status is booleans only. |
| `publish.py` | One-click **Netlify** deploy (file-digest protocol): only the generated site is uploaded; the site id is remembered so the URL stays stable. |
| `identify/` | **Identifier** providers → `Identification`. `tesseract` (default), `claude`, `ollama`. |
| `metadata/` | **MetadataProvider** providers → a per-type `*Meta`. Movies: `wikidata` (default), `tmdb`, `omdb`. Music: `musicbrainz` + Cover Art Archive, `discogs`. Books: `openlibrary`. Games: `games.py` (`GameMeta`, Wikidata `P31`=video game, platform → `format`). Audiobooks: `audiobook.py` (`AudiobookMeta`, Open Library + LibriVox). `upcitemdb` resolves movie UPCs. |
| `inventory.py` | Builds the self-contained, print-ready **`inventory.html`** (`export --format inventory`) — grouped by media type with per-type and grand-total estimated value; the browser's Print → Save-as-PDF makes the PDF (zero deps). |
| `events.py` | The compact, append-only change log (`data/events.jsonl`): integer timestamps, one-char ops, field-*names*-only for changes; self-trims; **excluded from publish**. Backs the `mediahound log` subcommand. |
| `links.py` | Where-to-watch/-listen/-play deep-links per media type (incl. platform-aware game storefronts: eShop / PS Store / Xbox / Steam + MobyGames). |
| `intro.py` | The enticing 1–2 sentence hook (identifier-written → tagline → templated). |
| `resale.py` | Heuristic used-value estimate + eBay sold-listings link; `estimate(..., media_type=...)` adds platform-aware game baselines and a **PriceCharting** price-check link, and Discogs price suggestions for music. |
| `streaming.py` | Where-to-watch via JustWatch's public GraphQL (no key). |

### Provider interfaces (extension points)
- `identify.base.Identifier.identify(image_path, jpeg_bytes) -> Identification`
- `metadata.base.MetadataProvider.lookup(title, year) -> *Meta`

Register a new one in the matching `__init__.py` factory. Adding a **media type** is deliberately
small: a provider here plus one entry in the shared media-type registry (the frontend's `TYPES` map in
`web/assets/js/app.js` and the backend's `_finalize_media` tail) — not a new branch in every module.
Moving an item between types preserves shared fields (e.g. `publisher` across book↔game) and clears
the old type's exclusive ones. See [CONTRIBUTING.md](CONTRIBUTING.md).

## The data folder (`<site>/data/`)

Generated (the site reads these):
- `collection.json` — the catalog (one object per title).
- `unidentified.json` — covers awaiting manual identification.
- `manifest.json` — `sha256 → {file, status, movie_id}`; drives incremental builds.
- `site.json` — title, subtitle, counts, admin password **hash** (never the plaintext).
- `view-config.json` — admin-owned: fields shown, default columns, library name/logo/description.
- `bundle.js` — all of the above embedded as `window.MEDIAHOUND_DATA` so `index.html` works from `file://`. Its sha (with the shell assets) is the cache-bust version stamped into the HTML `?v=` query strings and the service-worker cache name.

Audit / on-demand outputs:
- `events.jsonl` — the compact append-only change log (see `events.py`); **excluded from publish**.
- `inventory.html` — the printable inventory written by `export --format inventory` (or the admin
  Export menu's "🖨 Printable inventory (PDF)", built client-side); not part of the catalog bundle.

Round-trip files (exported by the admin UI, dropped back into `data/`, applied on next build):
- `corrections.json` — renames, format/studio edits, deletes, rotations, default-image, re-query flags.
- `seen-overrides.json` — permanent seen state + dates.
- `identify-queue.json` — manual names / discards for unidentified covers.

Posters live in `posters/` (downloaded art or cover-photo fallbacks); full cover photos in `originals/`.

## The web app (`mediahound/web/`)

Vanilla JS + CSS, **no framework, no build step**:
- `index.html` + `assets/js/app.js` — the catalog, filters, image gallery/zoom, and the admin tools.
- `identify.html` + `assets/js/identify.js` — manual identification.
- `assets/css/styles.css` — the dark, responsive theme.
- `sw.js` + `manifest.json` — the PWA service worker (offline shell) and install manifest.

Rendering & layout details:
- **Virtualized grid** — `render()` paints a 60-card chunk and appends more via an
  `IntersectionObserver` sentinel as the user scrolls, so a multi-thousand-item catalog starts with
  ~60 DOM nodes instead of all of them (covers are also `loading="lazy"`). Filtering/search resets the
  window; absent `IntersectionObserver` it renders everything.
- **Container-query cards** — `.card` is a query container; the fixed row heights that keep cards
  aligned across columns apply only in the dense grid (`@container (max-width: 320px)`), while wide /
  single-column cards flow at natural height with one uniform gap and empty optional rows collapse.
- **A–Z jump rail** — for title-sorted lists of 80+ items; clicking a letter renders up to that item
  and scrolls it below the sticky header (buckets by raw first char to match the `localeCompare` sort).
- **Mobile-first chrome** — below 640px the filter row collapses behind a **Filters** toggle, the
  header condenses, tap targets are ≥44px, and the grid is two columns (one below 380px).
- **Consistent icons** — per-card creator/label icons are an inline-SVG set (not OS-dependent emoji).
- Per-card field rows and where-to-X links are driven by the shared **`TYPES`** registry (see below).

Two modes: a read-only **default** view, and an **admin** view unlocked by SHA-256-comparing the
typed password against `site.admin_password_sha256`. When the site is opened through
`mediahound serve --admin` / `app` / `gui`, admin edits POST to the localhost write API and persist
straight to `data/` (and photo/CSV/keys/publish actions are available); when opened as plain static
files, edits live in `localStorage` and are exported as the round-trip JSON files above. The only
other network calls the site makes are the outbound "watch" / "sell" / "more info" links you click.

### The local write API (`serve --admin`)

A small same-origin-guarded HTTP API, **bound to `127.0.0.1`**: `/api/corrections|seen|identify`
(persist edits), `/api/upload` (drag-and-drop a cover), `/api/import` (CSV), `/api/rebuild`,
`/api/keys` (store API keys in the keychain — localhost only), `/api/publish` (deploy to Netlify —
localhost only). `--phone` adds a **per-session token** required on every write (constant-time
compare) so a phone on the LAN can upload without opening the API to other devices.

## Tooling (`tools/`)

Standalone maintenance scripts (not part of the installed package) for bulk-importing a large existing
music collection from disk and improving its metadata:
- `music_to_mediahound_csv_clean.py` — walk a tagged music library and emit a clean import CSV:
  balanced-bracket title cleanup, **global** artist canonicalization, genre normalization,
  audiobook/placeholder detection (routed to a review CSV), and folder-name recovery for `(Single)` /
  `[non-album]` album tags.
- `enrich_music_library.py` — resumable MusicBrainz/Cover-Art-Archive pass that fills missing
  covers/year/genre on an existing library, saving incrementally and skipping already-enriched items.
- `fetch_covers_itunes.py` — validated iTunes-Search cover fallback for albums MusicBrainz missed;
  accepts a result only when album+artist validate by token overlap (no wrong covers), unmatched items
  go to `covers-residual.csv`.

## Design principles

- **Offline by default** — building never hits the network unless `--online` is passed.
- **No secrets in the repo** — keys live in a gitignored `.env` **or the OS keychain** (set in the
  admin console); only a password *hash* ships. The write API and key/publish endpoints are
  localhost-only.
- **Degrade gracefully** — a failed lookup, rate-limited key, or unreadable cover never crashes a
  build or drops a title; it becomes a manual entry with your cover photo.
- **Trust the photo** — the identified name is authoritative; a fuzzy metadata match that returns a
  different film is rejected so it can't overwrite your data.
- **Incremental** — only new photos are processed; results are cached.
