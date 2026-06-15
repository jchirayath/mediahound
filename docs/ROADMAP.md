# Roadmap

What's shipped, what's designed next, and the idea backlog. Not a commitment — a shared map.

## ✅ Shipped (0.1 → 0.4.0)

Movies **and** music catalog · offline-first, zero-key default · OCR / Claude / Ollama identify ·
TMDB / OMDb / Wikidata / MusicBrainz metadata · where-to-watch & where-to-listen · resale estimates ·
CSV import/export · `serve --admin` live persistent editing · move titles Movies↔Music ·
**`mediahound app`** · **drag-and-drop + 📱 phone upload (QR)** · **desktop app (signed/notarized)** ·
**API keys in the OS keychain** · **🌐 one-click Publish (Netlify)** · brand/logo · PRIVACY.md.

**0.4.0:** 📷 **Barcode/UPC scanning** · 💿 **Discogs** (import + pricing) · 🛟 **backup/restore + Letterboxd/JSON
exports + JSON/RSS feeds** · ⭐ **personal catalog** (ratings/notes/tags/lending/surprise-me) · 📚 **library
switcher** · ❓ **inline Help** · decluttered **sticky two-row UI + action menus** · **rebrand** (beagle/Fredoka/orange)
· 📱 **PWA** (installable mobile app) · native **45 MB** Mac build.

**Post-0.4.0:** 📚 **Books** (ISBN → Open Library) · 🎮 **Video games** (title/UPC → Wikidata,
platform-as-format, where-to-play, PriceCharting resale) · 🎧 **Audiobooks** (Open Library + LibriVox,
narrator/duration, where-to-listen) — all zero-key, all built on a **shared media-type registry**
(card widgets + per-type fields are data-driven, so a new type is one registry entry, not a new branch
everywhere). Plus 🎵 **album track-info** (tracklists shown + searchable by song), a compact **change
log** (`events.jsonl`), a **printable PDF inventory** (`export --format inventory`), and **real demo
cover art** for every type.

## 🔜 Designed, planned next

See [`docs/design/`](design/):

5. **[New media types](design/05-new-media-types.md)** — 📚 Books & 🎮 Games **shipped**; the registry it
   introduced is the foundation for the media types below.

(Proposals 01–04 shipped in 0.4.0; Books + Games shipped post-0.4.0.)

## 🗂️ Backlog (not yet designed)

Captured for later. Roughly highest-value first.

| Idea | What it is | Why | Effort |
|---|---|---|---|
| **Collection insights / value dashboard** | Stats page: total resale value, counts by media type/format/genre/decade, "480 hours of movies · 1,200 albums," most-valuable items | Leans into the resale identity; we already compute per-item value | M |
| **"For sale" mode** | Select items → generate ready-to-paste eBay/Marketplace listings (title, photos, condition, suggested price) | Turns the catalog into a selling tool | M |
| **Duplicate detection** | Flag same title across formats / accidental double-catalogs (by barcode, title+year) | Cleanup; pairs with barcode + Discogs | S |
| **Condition & purchase tracking** | Per-item condition, purchase price/date → appreciation + insurance export | Collectors & insurance | S |
| **Wishlist / "want" list** | Track media you want to acquire, separate from owned | Natural companion to a collection | S |
| **Local vision identify (Ollama)** | Offline cover identification via a local model | Fully-offline accuracy without cloud keys | M |
| **Dark/light theme + a11y pass** | Theme toggle and accessibility audit | Polish | S |
| **Loan reminders / notifications** | "Out for 90 days" nudges (needs a notification surface) | Follow-on to lending tracker | M |

> Adding an idea here? Keep it one row; promote it to a `docs/design/NN-*.md` proposal when it's next.
