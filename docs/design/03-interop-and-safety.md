# 03 — Interop & safety

**Status:** ✅ Shipped (0.4.0) · **Effort:** S–M · **Depends on:** nothing

Four related capabilities: **backup/restore** (protect curation work), **exports** (Letterboxd /
Discogs / generic JSON), **feeds** (JSON/RSS), and **multiple libraries** (switcher in the app).

## Why

A user's real investment is their **curation** — manual titles, ratings, tags, corrections. That lives
in a handful of `data/*.json` files and is irreplaceable. We should make it trivial to **back up**,
**move between services**, and **subscribe to**. And power users want **more than one** catalog.

## 3a. Backup / restore (highest safety value)

- **`mediahound/backup.py`**: `make_backup(cfg, out.zip)` bundles `RawImages/` + `data/` +
  `config.toml` (the source-of-truth set). **Excludes `.env`** and the keychain (secrets never in a
  backup). `restore_backup(zip, dest)` re-creates a library.
- **CLI:** `mediahound backup [-o lib.zip]`, `mediahound restore lib.zip <dir>`.
- **Admin API / UI:** `POST /api/backup` streams a zip download; an **⬇ Backup** button. Restore is
  CLI/desktop only (it writes a whole library).
- **Desktop:** offer "Back up library…" in the app menu.

## 3b. Exports

- **`mediahound/exporters.py`**:
  - **Letterboxd** (movies) — CSV in their import schema (`Title, Year, Rating10, WatchedDate, Tags`),
    driven by personal ratings/seen (proposal 04). `mediahound export --format letterboxd`.
  - **Discogs** (music) — a CSV of release ids / catalog #s for re-import, or (P3) push owned releases
    to a Discogs folder via the API (token from keychain).
  - **Generic JSON** — the catalog is already `collection.json`; document the schema as a stable export.
- **Admin UI:** an **Export ▾** menu (Letterboxd CSV / catalog CSV / JSON).

## 3c. Feeds

- During `pipeline._write_site`, also emit **`feed.json`** ([JSON Feed](https://jsonfeed.org)) and
  **`feed.xml`** (RSS) of *recently added* items (title, art, link). Zero new deps; published with the
  site so anyone can subscribe or integrate. Off by a config flag if undesired.

## 3d. Multiple libraries / profiles

- A library is already just a directory. Add a **recent-libraries** list (small JSON in the user's app
  dir, e.g. `~/.config/mediahound/recent.json`) and a **switcher** in the desktop app: open / create /
  switch library. CLI already takes `--config` / a directory.
- Use cases: separate movies vs. music catalogs, or per-family-member collections.

## Privacy / offline

Backups and exports are **local files**. Feeds are only public if the user **Publishes** the site
(noted in PRIVACY.md). Discogs push (P3) is the only outbound write and is explicit + token-gated.

## Phasing

1. **P1** — **backup/restore** (CLI + `/api/backup`) and **JSON feed**.
2. **P2** — **Letterboxd CSV** export + **RSS** feed.
3. **P3** — multi-library switcher in the desktop app; Discogs push export.

## Testing

- Round-trip: `make_backup` → `restore_backup` reproduces `data/` byte-for-byte and **omits `.env`**.
- Letterboxd CSV matches their column spec; feed.json validates against the JSON Feed schema.

## Open questions

- Backup size with `RawImages/` (full photos) — offer a `--no-photos` (data-only) variant for quick,
  small backups of just the curation.
- iCloud/Dropbox already sync the library folder transparently — document that as the "cloud backup"
  story rather than building our own.
