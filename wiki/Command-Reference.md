# Command Reference

All commands read paths from `config.toml` (resolved relative to that file).

## `mediahound init <dir>`
Scaffold a new site folder (template + `config.toml`). `--force` overwrites template files.

## `mediahound build`
Process **new** cover photos and (re)generate the catalog. Incremental — only unseen images
(tracked by sha256) are processed.

| Flag | Meaning |
| --- | --- |
| `--online` | Allow metadata / where-to-watch lookups. **Default is offline** (regenerate from existing data). |
| `--refresh-streaming` | Re-check where-to-watch for every title (implies `--online`). |
| `--force` | Reprocess every image, not just new ones. |
| `--reidentify <hash>` | Reprocess a single image by its sha256. |
| `--limit <N>` | Process at most N new images this run. |
| `--mock` | Demo with bundled sample data (no providers/keys). |

## `mediahound app [dir]`
**The easy button.** Sets up a library (default `./MediaHound-Library`) if needed, then opens the
editor in your browser with the write API on — no other commands to remember.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--phone` | off | Open to your Wi-Fi and print a **QR code** so you can add photos from your phone. Uploads are token-protected; localhost-only actions (API keys, publish) stay disabled. Trusted networks only. |
| `--port <N>` | `8765` | Port. |
| `--host <H>` | `127.0.0.1` | Bind address. |
| `--no-open` | off | Don't auto-open a browser. |

## `mediahound gui [dir]`
Open the editor in a **native desktop window** (the bundled `.app` / `.exe` runs this). Library
defaults to `~/MediaHound Library`. Needs the `desktop` extra (`pip install "mediahound[desktop]"`);
falls back to the browser without it.

## `mediahound serve`
Preview the generated site locally over http (avoids `file://` fetch limits).

| Flag | Default | Meaning |
| --- | --- | --- |
| `--admin` | off | Enable the **localhost write API** — admin-portal edits (and photo upload, CSV import, API keys, publish) save straight to `data/` and survive every rebuild. See **[[Editing and Persisting Changes]]**. |
| `--port <N>` | `8765` | Port. |
| `--host <H>` | `127.0.0.1` | Bind address (keep admin on localhost). |
| `--no-open` | off | Don't auto-open a browser. |

> **Security:** the write API is a local authoring tool. It binds to `127.0.0.1` and refuses
> cross-origin writes; **API-key and publish actions are localhost-only** (refused over `--phone`).
> Never expose it publicly; public hosting serves the plain static files.

### Admin-console actions (under `app` / `serve --admin` / `gui`)
Grouped into a few menus to keep the bar tidy:
- **➕ Add** — drag-and-drop **photos**, **📷 Scan barcode** (UPC/EAN → the exact release), or **import a CSV**.
- **🔗 Connect** — **import from Discogs**, **🌐 Publish** to the web (Netlify), or **export to Letterboxd**.
- **⤓ Export** — catalog **CSV** / **JSON**, your **edits**, or **seen** marks.
- **💾 Backup** — back up the whole library / **data only**, or restore.
- **📚 Library** — open / create / **switch** between catalogs (the **data directory** lives in each `config.toml`).
- **⚙ Settings → API keys** — store TMDB / OMDb / Anthropic / **Discogs** keys in the **OS keychain** (write-only).
- **↻ Rebuild** — re-bake the catalog from your saved edits.
- **⭐ Personal catalog** — rate (★1–10), note, tag/shelve, and track lending; admin-only, never published.

## `mediahound import <file.csv>`
Bulk-add movies & music from a CSV (no photos needed). `--online` enriches each row.

## `mediahound import-discogs <username>`
Import a Discogs user's record/CD collection. `--token` / `--token-from-keychain` raise the rate limit
and enrich each release; `--offline` skips per-release lookups.

## `mediahound export`
Write the catalog out: `--format csv` (full catalog, default), `--format letterboxd` (movies → a
Letterboxd import CSV), or `--format json`. `-o <path>` sets the output.

## `mediahound backup` / `mediahound restore`
- `mediahound backup [-o lib.zip] [--no-photos]` — zip your library (RawImages + data + config);
  `--no-photos` is a quick, small **curation-only** backup. Secrets (`.env`) are never included.
- `mediahound restore <backup.zip> <dir>` — re-create a library from a backup into a new folder.
