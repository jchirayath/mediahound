# Design proposals

Integrations (all now shipped), designed against MediaHound's existing architecture (the identify/metadata
**provider** interfaces, the `data/` override files that survive every rebuild, the localhost
**admin write API**, and the offline-first / no-telemetry posture in [PRIVACY.md](../../PRIVACY.md)).

| # | Proposal | One-liner | Status |
|---|---|---|---|
| 01 | [Barcode / UPC scanning](01-barcode-scanning.md) | Identify by barcode (exact) instead of OCR (fuzzy) | Implemented |
| 02 | [Discogs integration](02-discogs-integration.md) | Make the music half best-in-class: import + pricing | Implemented |
| 03 | [Interop & safety](03-interop-and-safety.md) | Backup/restore, exports (Letterboxd…), feeds, multi-library | Implemented |
| 04 | [Personal catalog](04-personal-catalog.md) | Ratings, notes, shelves/tags, lending, "surprise me" | Implemented |
| 05 | [New media types: Books, Video games & Audiobooks](05-new-media-types.md) | ISBN/UPC → Open Library / Wikidata; LibriVox; a shared media-type registry | Implemented (📚 Books · 🎮 Games · 🎧 Audiobooks) |

> **Status note (shipped).** All five proposals are implemented — including proposal 05's three new
> media types: 📚 books (Open Library), 🎮 video games (Wikidata, platform-aware PriceCharting resale)
> and 🎧 audiobooks (Open Library + LibriVox), added through a shared media-type registry
> (`TYPES` map + `_finalize_media`). Delivered: barcode decode (`mediahound/barcode.py`,
> core `zxing-cpp` — photograph the barcode to add) + music UPC→MusicBrainz/Discogs + movie UPC→UPCItemDB + a `📷 Scan barcode`
> UI; the Discogs provider (`metadata/discogs.py`), `import-discogs` CLI/API, and price suggestions;
> `backup`/`restore` (`backup.py`), Letterboxd/JSON exporters (`exporters.py`), JSON+RSS feeds, and a `⬇ Backup`
> button; and personal ratings/notes/tags + lending + 🎲 Surprise-me, with all personal data stripped from the
> published catalog. The **multi-library switcher** (3d) is also implemented — a `📚 Library` admin dialog backed
> by `~/.config/mediahound/recent.json` that opens / creates / **live-switches** the served library without a
> restart (localhost-only). Remaining deferred sub-item: Discogs push-export (3b/P3).

Deferred ideas live in the [Roadmap / backlog](../ROADMAP.md).

## Cross-cutting principles (apply to all five)

- **Offline by default.** New network calls (UPC lookups, Discogs) only happen under `--online` /
  explicit actions, never on a plain build. ([PRIVACY.md](../../PRIVACY.md))
- **Edits persist to `data/`.** Personal data (ratings, tags, loans) uses the same override-file
  pattern as `corrections.json` / `seen-overrides.json`, so it survives every `mediahound build`.
- **Secrets in the keychain.** New tokens (Discogs) go through `keystore.py`, never a file.
- **Public vs. private.** Personal/loan data is **admin-only** and stripped from the published bundle.
- **Reuse the pipeline.** Prefer "resolve to a title/release → feed existing providers" over new
  bespoke paths, so all media types stay consistent.
