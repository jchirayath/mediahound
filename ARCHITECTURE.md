# ReelShelf — Architecture

ReelShelf is two halves that meet at a folder of JSON files:

1. A **Python CLI** (`reelshelf/`) that reads cover photos and writes a catalog.
2. A **static, dependency-free web app** (`web/`) that renders that catalog.

They never talk at runtime — the CLI produces files; the site reads them.

```
┌─────────────────────────── reelshelf build ───────────────────────────┐
│                                                                        │
│  RawImages/*.jpg                                                       │
│      │  sha256 → data/manifest.json   (incremental: skip already-done) │
│      ▼                                                                  │
│  identify  ──────────────►  Identification(title, year, format, …)     │
│  (tesseract | claude | ollama)                                         │
│      │                                                                  │
│      ▼ confidence ≥ threshold?                                         │
│   ┌──┴───────────────┐ no → data/unidentified.json → identify.html     │
│   │ yes                                                                 │
│   ▼                                                                     │
│  enrich  ───────────────►  MovieMeta(poster, genres, cast, studio, …)  │
│  (wikidata | tmdb | omdb)   + plausible-title guard + on-disk cache    │
│      │                                                                  │
│      ▼                                                                  │
│  intro (hook) + resale (eBay) + where-to-watch (JustWatch)             │
│      │                                                                  │
│      ▼                                                                  │
│  data/collection.json   posters/   originals/   data/bundle.js         │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
            web/index.html + assets/js/app.js  (vanilla JS, no build step)
```

## Python package (`reelshelf/`)

| Module | Responsibility |
|---|---|
| `cli.py` | `reelshelf init <dir>` and `reelshelf build` (argparse). |
| `config.py` | Loads `config.toml`, merges defaults, loads `.env` secrets, resolves paths. |
| `pipeline.py` | Orchestration: scan → identify → enrich → intro/resale/streaming → write. Also `--mock`, corrections, offline/online gating, and the metadata cache + plausibility guard. |
| `store.py` | The incremental `manifest.json` and the JSON the website reads (collection / unidentified). Merges duplicate photos into one gallery; applies seen/corrections. |
| `imaging.py` | Pillow helpers: prepare a compact JPEG for OCR/vision, save thumbnails, auto-upright landscape covers, rotate, placeholder posters for `--mock`. |
| `identify/` | **Identifier** providers → `Identification`. `tesseract` (default), `claude`, `ollama`. |
| `metadata/` | **MetadataProvider** providers → `MovieMeta`. `wikidata` (default), `tmdb`, `omdb`. |
| `intro.py` | The enticing 1–2 sentence hook (identifier-written → tagline → templated). |
| `resale.py` | Heuristic used-value estimate + eBay sold-listings link. |
| `streaming.py` | Where-to-watch via JustWatch's public GraphQL (no key). |

### Provider interfaces (extension points)
- `identify.base.Identifier.identify(image_path, jpeg_bytes) -> Identification`
- `metadata.base.MetadataProvider.lookup(title, year) -> MovieMeta`

Register a new one in the matching `__init__.py` factory. See [CONTRIBUTING.md](CONTRIBUTING.md).

## The data folder (`<site>/data/`)

Generated (the site reads these):
- `collection.json` — the catalog (one object per title).
- `unidentified.json` — covers awaiting manual identification.
- `manifest.json` — `sha256 → {file, status, movie_id}`; drives incremental builds.
- `site.json` — title, subtitle, counts, admin password **hash** (never the plaintext).
- `view-config.json` — admin-owned: fields shown, default columns, library name/logo/description.
- `bundle.js` — all of the above embedded as `window.REELSHELF_DATA` so `index.html` works from `file://`.

Round-trip files (exported by the admin UI, dropped back into `data/`, applied on next build):
- `corrections.json` — renames, format/studio edits, deletes, rotations, default-image, re-query flags.
- `seen-overrides.json` — permanent seen state + dates.
- `identify-queue.json` — manual names / discards for unidentified covers.

Posters live in `posters/` (downloaded art or cover-photo fallbacks); full cover photos in `originals/`.

## The web app (`web/`)

Vanilla JS + CSS, **no framework, no build step**:
- `index.html` + `assets/js/app.js` — the catalog, filters, image gallery/zoom, and the admin tools.
- `identify.html` + `assets/js/identify.js` — manual identification.
- `assets/css/styles.css` — the dark, responsive theme.

Two modes: a read-only **default** view, and an **admin** view unlocked by SHA-256-comparing the
typed password against `site.admin_password_sha256`. Admin edits persist to `localStorage` and are
exported as the round-trip JSON files above. The only network calls the site makes are the outbound
"watch" / "sell" / "more info" links you click.

## Design principles

- **Offline by default** — building never hits the network unless `--online` is passed.
- **No secrets in the repo** — keys only in a gitignored `.env`; only a password *hash* ships.
- **Degrade gracefully** — a failed lookup, rate-limited key, or unreadable cover never crashes a
  build or drops a title; it becomes a manual entry with your cover photo.
- **Trust the photo** — the identified name is authoritative; a fuzzy metadata match that returns a
  different film is rejected so it can't overwrite your data.
- **Incremental** — only new photos are processed; results are cached.
