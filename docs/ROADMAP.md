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

**Post-0.4.0:** 📚 **Books** (ISBN → Open Library, zero-key) · 🎮 **Video games** (title/UPC → Wikidata,
zero-key; platform-as-format; where-to-play links) — both built on a **shared media-type registry**
(card widgets + per-type fields are data-driven, so a new type is one registry entry, not a new branch
everywhere).

## 🔜 Designed, planned next

See [`docs/design/`](design/):

5. **[New media types](design/05-new-media-types.md)** — 📚 Books & 🎮 Games **shipped**; the registry it
   introduced is the foundation for the media types below.

(Proposals 01–04 shipped in 0.4.0; Books + Games shipped post-0.4.0.)

## 🗂️ Backlog (not yet designed)

Captured for later. Roughly highest-value first.

| Idea | What it is | Why | Effort |
|---|---|---|---|
| **Common event log (compact)** | Append-only audit of every add / remove / change to the catalog (and corrections/seen/loans), as space-efficient as possible (short-key JSONL, deltas only, capped/rotated). Admin-only, never published. | Undo/history, "what changed when," sync groundwork | S–M |
| **🎵 Album track search** | Resolve an album's tracklist from its title, then let search match on song titles (not just album/artist) | Find a record by a song on it | S |
| **🎧 Audiobooks** | Audiobook as a first-class media type (narrator, runtime, ISBN/ASIN) — likely a `book` format or sibling type via the registry | Natural companion to Books | S–M |
| **🎮 Games resale (PriceCharting)** | Used-price + sold-listing links for games by platform (retro especially) | Games resell well; matches the resale identity | S |
| **Collection insights / value dashboard** | Stats page: total resale value, counts by format/genre/decade, "480 hours of movies," most-valuable items | Leans into the resale identity; we already compute per-item value | M |
| **"For sale" mode** | Select items → generate ready-to-paste eBay/Marketplace listings (title, photos, condition, suggested price) | Turns the catalog into a selling tool | M |
| **Duplicate detection** | Flag same title across formats / accidental double-catalogs (by barcode, title+year) | Cleanup; pairs with barcode + Discogs | S |
| **Condition & purchase tracking** | Per-item condition, purchase price/date → appreciation + insurance export | Collectors & insurance | S |
| **Wishlist / "want" list** | Track media you want to acquire, separate from owned | Natural companion to a collection | S |
| **Local vision identify (Ollama)** | Offline cover identification via a local model | Fully-offline accuracy without cloud keys | M |
| **PDF / printable inventory** | A printable catalog/inventory export | Insurance, sharing offline | S |
| **Dark/light theme + a11y pass** | Theme toggle and accessibility audit | Polish | S |
| **Loan reminders / notifications** | "Out for 90 days" nudges (needs a notification surface) | Follow-on to lending tracker | M |

> Adding an idea here? Keep it one row; promote it to a `docs/design/NN-*.md` proposal when it's next.
