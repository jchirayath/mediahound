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
| `pipeline.py` | Orchestration: scan → identify → enrich → intro/resale/streaming → write. Also `--mock`, corrections, offline/online gating, and the metadata cache + plausibility guard. The shared **`_finalize_media`** helper is the common per-type tail (cover, resale, links, write), so each media type is a thin enrich function, not a duplicated branch. |
| `store.py` | The incremental `manifest.json` and the JSON the website reads (collection / unidentified). Merges duplicate photos into one gallery; applies seen/corrections. |
| `imaging.py` | Pillow helpers: prepare a compact JPEG for OCR/vision, save thumbnails, auto-upright landscape covers, rotate, placeholder posters for `--mock`. |
| `serve.py` | `serve` previews the site; `serve --admin` exposes a **localhost-only write API** so admin edits save straight to `data/` (+ photo upload, CSV import, rebuild, API-keys, publish). `--phone` binds to the LAN with a **per-session token + QR** for uploading from a phone. |
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
- `bundle.js` — all of the above embedded as `window.MEDIAHOUND_DATA` so `index.html` works from `file://`.

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
