# 02 — Discogs integration

**Status:** ✅ Shipped (0.4.0) · **Effort:** M · **Depends on:** keystore (done); pairs with [Barcode](01-barcode-scanning.md)

## Why

Music currently leans on MusicBrainz + Cover Art Archive (metadata) and eBay (resale). **Discogs** is
*the* database and marketplace for records and CDs. Integrating it roughly doubles the value of the
music half:

1. **Import an existing Discogs collection** — many vinyl owners already maintain one; instant catalog.
2. **Accurate pricing** — Discogs price-suggestions by condition beat generic eBay estimates for vinyl.
3. **Richer metadata** — exact pressing, label, catalog #, styles, tracklist, barcode.

## User stories

- *Import:* "I have 300 records in Discogs" → `mediahound import-discogs <username>` (or a button) →
  they're all in my catalog with art and metadata.
- *Pricing:* each record shows a realistic **resale estimate** from Discogs, by condition.
- *Identify:* scanning a record's barcode resolves to the exact Discogs release (with proposal 01).

## Discogs API notes

- **Auth:** a personal access token; rate-limited (~60 req/min). Requires a descriptive `User-Agent`.
- **Collection:** `GET /users/{user}/collection/folders/0/releases` (paginated).
- **Release:** `GET /releases/{id}` → artist, title, year, labels, catalog #, formats, tracklist,
  genres/styles, images, **barcode**.
- **Search:** `GET /database/search?barcode=<upc>` and `?release_title=&artist=`.
- **Pricing:** `GET /marketplace/price_suggestions/{release_id}` → price by condition (token-gated).

## Architecture

- **`mediahound/metadata/discogs.py`** (new) — a `MetadataProvider` for **music**: `lookup(title,
  year)` and `lookup_by_barcode(upc)` → `MusicMeta` (cover, artist, label, catalog #, tracklist,
  genres). Selectable in `config.toml` as a music metadata provider, or as a fallback after MusicBrainz.
- **`mediahound/discogs_import.py`** (new) — fetch a user's collection, map each release →
  `media_type=music` catalog item (the same shape `import_csv` produces), enrich via the release
  endpoint. Reuses the importer's upsert path.
- **`resale.py`** — add `discogs_price(release_id, condition)`; for music items with a Discogs release
  id, prefer it over the eBay heuristic (keep eBay as fallback / for movies).
- **`keystore.py`** — add `DISCOGS_TOKEN` to the allow-list; surface it in **Settings → API keys**.
- **Admin API** (`serve.py`) — `POST /api/import-discogs {username}` (localhost-only, like `/api/import`).
- **CLI** — `mediahound import-discogs <username> [--token-from-keychain]`.

## Data model

Store `discogs_release_id` (and `catalog_no`, `barcode`) on music items — enables exact re-pricing and
dedup. Settable via corrections so it survives rebuilds.

## Dependencies

Just `requests` (already a dep). Implement polite rate-limiting + a custom User-Agent string
(`mediahound/<version> +https://github.com/jchirayath/mediahound`). Reuse the metadata cache.

## Privacy / offline

All Discogs calls are online and explicit (import / `--online` / Publish never involved). Token lives
in the OS keychain. Importing reads *your* public/owned collection only; nothing is written back to
Discogs (export-to-Discogs is scoped in proposal 03).

## Phasing

1. **P1** — Discogs **metadata provider** (lookup by barcode/title) + `DISCOGS_TOKEN` storage.
2. **P2** — **Collection import** (`import-discogs` + admin button).
3. **P3** — **Price suggestions** wired into `resale.py` for music.

## Testing

Mock Discogs JSON (collection page, release, search, price-suggestions). Assert mapping → `MusicMeta`,
rate-limit backoff, and that resale prefers Discogs for music with a release id.

## Open questions

- Match imported releases to any existing photo-based items (by barcode/catalog #) to avoid duplicates
  → ties into the dedup idea in the [Roadmap](../ROADMAP.md).
- Pricing currency/locale handling.
