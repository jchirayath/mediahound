# 01 — Barcode / UPC scanning

**Status:** ✅ Shipped (0.4.0) · **Effort:** M · **Depends on:** nothing (pairs with [Discogs](02-discogs-integration.md))

## Why

OCR on a cover photo is the weakest link in identification — fuzzy, language-sensitive, and the
plausible-title guard rejects near-misses. A **barcode** (UPC-A / EAN-13) on the back of a DVD, CD, or
record sleeve identifies the exact release. This is the single biggest accuracy + speed win, and it
slots straight into the existing phone-upload flow.

## User stories

- *On my phone:* point the camera at a barcode → the title pops up identified → confirm → it's in my
  catalog. No typing, no cover photo needed.
- *On my desktop:* drop a photo of the **back** of the case → MediaHound reads the barcode and
  identifies it exactly.
- *CLI:* `mediahound build` finds a barcode in a `RawImages/` photo and prefers it over OCR.

## How identification works (reuse the pipeline)

```
barcode (image decode OR phone scan)
        │  UPC/EAN string
        ▼
   route by media_type
   ┌─────────────┴───────────────┐
   ▼ music                        ▼ movie
 MusicBrainz / Discogs           product-UPC lookup (UPCItemDB)
 barcode search → exact release  → product title → existing TMDB/Wikidata/OMDb identify
```

- **Music is the sweet spot:** MusicBrainz supports `query=barcode:<upc>` and Discogs supports
  `database/search?barcode=` — both return the exact release. Very accurate, free.
- **Movies have no great free UPC→film DB**, so resolve UPC → *product name* (UPCItemDB free tier, or
  similar) → feed that name into the **existing** identify-by-title path. No new movie pipeline.

## Architecture

- **`mediahound/barcode.py`** (new):
  - `decode_image(path) -> list[str]` — server-side decode (see deps).
  - `lookup(upc, media_type, cfg) -> Identification | None` — routes to MusicBrainz/Discogs (music) or
    UPCItemDB→title (movies). Returns the same `Identification` the OCR path produces.
- **Pipeline** (`pipeline.py`): when a photo decodes to a barcode, try `barcode.lookup()` **before**
  OCR; on success mark the identification source `barcode` (high confidence, skips the plausibility
  guard). Falls back to OCR if no barcode / no match.
- **Metadata** (`metadata/musicbrainz.py`): add `lookup_by_barcode(upc)`. New `metadata/upcitemdb.py`
  for product lookups (key-optional; free tier).
- **Admin API** (`serve.py`): `POST /api/identify-barcode {upc, media_type}` → returns the match for a
  one-tap confirm, then writes it like `/api/import`. `/api/upload` also accepts an optional `upc`.
- **Frontend**: a **📷 Scan barcode** mode in the Add-photos dialog (and the phone view). Uses the
  native [`BarcodeDetector`](https://developer.mozilla.org/docs/Web/API/BarcodeDetector) where
  available, else [`@zxing/browser`](https://github.com/zxing-js/library) as a fallback, all in-page.
  Decodes → POSTs the UPC → shows the matched title to confirm.

## Data model

Add `upc` to each item (in `collection.json`, settable via `corrections.json`). Useful later for
**dedup** and for **Discogs pricing** (barcode → release → price).

## Dependencies

- **Server decode:** prefer **`zxing-cpp`** (pip wheel, no system lib → bundles cleanly in the
  PyInstaller desktop app) over `pyzbar` (needs the `libzbar` system library). Shipped as a **core
  dependency** (so "photograph the barcode" works everywhere out of the box); `mediahound[barcode]`
  remains as a back-compat alias. `barcode.decode_image()` degrades to `[]` if the wheel is missing.
- **Client scan:** native `BarcodeDetector` (Chrome/Android) + `@zxing/browser` fallback (vendored, no
  build step — matches the no-framework frontend).

## Privacy / offline

Decoding is **local**. UPC→title lookups are network calls, gated behind `--online` / explicit scan
actions exactly like other enrichment. Nothing is sent on a plain build. Documented in PRIVACY.md.

## Phasing

1. **P1** — `barcode.py` decode from photos + **music UPC → MusicBrainz**; CLI + `/api/identify-barcode`.
2. **P2** — **live phone scanning** (BarcodeDetector / zxing-js) → instant identify. The headline UX.
3. **P3** — movie UPC resolver (UPCItemDB) + Discogs barcode search (with proposal 02).

## Testing

- Decode fixture images of known UPC/EAN codes (generate barcodes in tests).
- Mock MusicBrainz/UPCItemDB responses; assert the right release/title is chosen and the plausibility
  guard is bypassed for barcode-sourced matches.

## Open questions

- Bundle size: does `zxing-cpp` inflate the desktop app meaningfully? (Likely fine.)
- UPCItemDB free-tier rate limits — cache aggressively (reuse the metadata cache).
