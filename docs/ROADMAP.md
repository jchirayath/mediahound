# Roadmap

What's shipped, what's designed next, and the idea backlog. Not a commitment — a shared map.

## ✅ Shipped (0.1 → 0.3.1)

Movies **and** music catalog · offline-first, zero-key default · OCR / Claude / Ollama identify ·
TMDB / OMDb / Wikidata / MusicBrainz metadata · where-to-watch & where-to-listen · resale estimates ·
CSV import/export · `serve --admin` live persistent editing · move titles Movies↔Music ·
**`mediahound app`** · **drag-and-drop + 📱 phone upload (QR)** · **desktop app (signed/notarized)** ·
**API keys in the OS keychain** · **🌐 one-click Publish (Netlify)** · brand/logo · PRIVACY.md.

## 🔜 Designed, planned next

See [`docs/design/`](design/):

1. **[Barcode / UPC scanning](design/01-barcode-scanning.md)** — exact identification (vs. fuzzy OCR).
2. **[Discogs integration](design/02-discogs-integration.md)** — import collections + accurate music pricing.
3. **[Interop & safety](design/03-interop-and-safety.md)** — backup/restore, exports, feeds, multi-library.
4. **[Personal catalog](design/04-personal-catalog.md)** — ratings, notes, shelves/tags, lending, surprise-me.

## 🗂️ Backlog (not yet designed)

Captured for later. Roughly highest-value first.

| Idea | What it is | Why | Effort |
|---|---|---|---|
| **Collection insights / value dashboard** | Stats page: total resale value, counts by format/genre/decade, "480 hours of movies," most-valuable items | Leans into the resale identity; we already compute per-item value | M |
| **"For sale" mode** | Select items → generate ready-to-paste eBay/Marketplace listings (title, photos, condition, suggested price) | Turns the catalog into a selling tool | M |
| **Duplicate detection** | Flag same title across formats / accidental double-catalogs (by barcode, title+year) | Cleanup; pairs with barcode + Discogs | S |
| **Condition & purchase tracking** | Per-item condition, purchase price/date → appreciation + insurance export | Collectors & insurance | S |
| **Wishlist / "want" list** | Track media you want to acquire, separate from owned | Natural companion to a collection | S |
| **Books** | New media type: ISBN scan → Open Library / Google Books | Same pipeline, big new audience | M |
| **Video games** | New media type: cover/barcode → IGDB | Same pipeline, new audience | M |
| **Local vision identify (Ollama)** | Offline cover identification via a local model | Fully-offline accuracy without cloud keys | M |
| **PDF / printable inventory** | A printable catalog/inventory export | Insurance, sharing offline | S |
| **Dark/light theme + a11y pass** | Theme toggle and accessibility audit | Polish | S |
| **Loan reminders / notifications** | "Out for 90 days" nudges (needs a notification surface) | Follow-on to lending tracker | M |

> Adding an idea here? Keep it one row; promote it to a `docs/design/NN-*.md` proposal when it's next.
