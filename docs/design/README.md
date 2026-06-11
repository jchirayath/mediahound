# Design proposals

Planned integrations, designed against MediaHound's existing architecture (the identify/metadata
**provider** interfaces, the `data/` override files that survive every rebuild, the localhost
**admin write API**, and the offline-first / no-telemetry posture in [PRIVACY.md](../../PRIVACY.md)).

| # | Proposal | One-liner | Status |
|---|---|---|---|
| 01 | [Barcode / UPC scanning](01-barcode-scanning.md) | Identify by barcode (exact) instead of OCR (fuzzy) | Planned |
| 02 | [Discogs integration](02-discogs-integration.md) | Make the music half best-in-class: import + pricing | Planned |
| 03 | [Interop & safety](03-interop-and-safety.md) | Backup/restore, exports (Letterboxd…), feeds, multi-library | Planned |
| 04 | [Personal catalog](04-personal-catalog.md) | Ratings, notes, shelves/tags, lending, "surprise me" | Planned |

Deferred ideas live in the [Roadmap / backlog](../ROADMAP.md).

## Cross-cutting principles (apply to all four)

- **Offline by default.** New network calls (UPC lookups, Discogs) only happen under `--online` /
  explicit actions, never on a plain build. ([PRIVACY.md](../../PRIVACY.md))
- **Edits persist to `data/`.** Personal data (ratings, tags, loans) uses the same override-file
  pattern as `corrections.json` / `seen-overrides.json`, so it survives every `mediahound build`.
- **Secrets in the keychain.** New tokens (Discogs) go through `keystore.py`, never a file.
- **Public vs. private.** Personal/loan data is **admin-only** and stripped from the published bundle.
- **Reuse the pipeline.** Prefer "resolve to a title/release → feed existing providers" over new
  bespoke paths, so movies and music stay consistent.
