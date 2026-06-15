# How MediaHound compares

There are plenty of ways to catalog a movie collection. This is an honest look at the main
alternatives and where MediaHound fits. *Facts verified June 2026 from each product's own site/repo;
pricing and project status change — corrections welcome via PR.*

## The one-line landscape

Almost every existing tool adds items by **barcode scan, online title search, or manual entry**, and
keeps your catalog in **their cloud app** or a **dated desktop database**. MediaHound takes a different
path: it identifies titles from **photos of the covers** (OCR / optional AI vision) and generates a
**modern static website you own and host for free** — offline-first and open-source. It catalogs five
media types in one place: 🎬 movies, 🎵 music, 📚 books, 🎮 video games, and 🎧 audiobooks.

## Comparison

| Tool | Type / Platform | Open source | Price | Add items by | Catalog lives in | Self-host / own data |
|---|---|---|---|---|---|---|
| **MediaHound** | CLI → static website (any OS); movies, music, books, games & audiobooks | ✅ MIT | Free | **Photo of cover (OCR/AI)**, or manual | A static site you host (or open `index.html`) | ✅ Fully — plain files, host anywhere |
| CLZ Movies | Web + iOS/Android (cloud); **separate paid app per category** | ❌ | ~$20–40/yr (per category) | Barcode, title search | CLZ Cloud + share page | ❌ (CSV export only) |
| Libib | Web + iOS/Android (cloud); multi-category (books/movies/music/games) | ❌ | Free ≤5k items; Pro $99/yr | Barcode, title search | Libib Cloud + public OPAC (Pro) | ❌ (CSV export only) |
| My Movies | Windows desktop + mobile/web; **movies only** | ❌ | Free basic; ~$100 one-time | Barcode, title search, folder import | Local Windows DB + online view | ◻︎ Local DB, but cloud for online/sync |
| DVD Profiler | Windows desktop + mobile; **movies only** | ❌ | Freemium (one-time premium) | Barcode, title search | Local DB + Invelos online | ❌ — **dead/EOL in 2026** |
| GCstar | Desktop (Lin/Win/Mac) | ✅ GPL-2 | Free | Title search, manual, barcode add-on | Local DB; dated **static HTML export** | ✅ — but last release ~2023 (dormant) |
| Tellico | Desktop (Linux/KDE) | ✅ GPL | Free | Title search, manual, barcode | Local DB; templated **static HTML export** | ✅ — actively maintained (best of the OSS desktop apps) |
| Griffith | Desktop (Lin/Win/Mac) | ✅ GPL-2 | Free | Title search | Local DB; basic HTML export | ✅ — but **abandoned** (archived 2017) |
| Data Crow | Java desktop **+ self-hosted web** | ✅ GPL-3 | Free | Title search, file/metadata import, limited barcode | Self-hosted live web app | ✅ — strong; heavyweight Java, serves a live app |
| Plex / Jellyfin | Media **server** | Jellyfin ✅ / Plex ❌ | Free / freemium | Scans your **digital video files** | Private server you host | ✅ (Jellyfin fully; Plex needs an account) |
| Notion / Airtable | Cloud database (DIY) | ❌ | Free tier; paid plans | Manual; Airtable has phone barcode scan | Cloud DB + public share view | ❌ (proprietary SaaS) |

## What's genuinely different about MediaHound

1. **Identify from photos, not barcodes.** Every other tool needs a UPC/EAN or that you type the
   title. MediaHound reads the cover photo (Tesseract OCR by default, or Claude vision). This is the
   only practical path for **bulk-photographing a shelf** and for **VHS**, which mostly has no usable
   barcode/UPC in the disc databases the others depend on.
2. **You get a real, modern website — that you own.** The open-source desktop tools (GCstar, Tellico,
   Griffith) can export *static HTML*, but it's template-driven and dated; Data Crow serves a *live
   Java web app*. MediaHound outputs a polished, responsive, searchable site you can host **free** on
   GitHub Pages / Cloudflare / Netlify, or open by double-clicking `index.html`.
3. **No subscription, no account, no cloud lock-in.** CLZ, Libib, and My Movies' best features live in
   their cloud. MediaHound is offline-first and keeps everything in plain files you control.
4. **Right category for a *physical* shelf.** Plex and Jellyfin are excellent — but for **digital media
   files**, not an inventory of physical cases. DVD Profiler was the purpose-built physical-disc tool,
   but it appears end-of-life in 2026 (its server has been unresponsive).
5. **One catalog, five media types.** Most rivals are single-category (and CLZ charges *per* category).
   MediaHound covers 🎬 movies, 🎵 music, 📚 books, 🎮 video games, and 🎧 audiobooks side by side, all
   resolved from **zero-key public data** (Wikidata/TMDB/OMDb, MusicBrainz, Open Library, LibriVox).
6. **Extras the catalogers don't combine:** where-to-watch / -listen / -play links, used **resale value**
   with eBay sold-listings links (plus PriceCharting for games and Discogs for music), a built-in
   admin/curation UI, and a one-click **printable inventory (PDF)** with per-type and grand-total value.

## Where MediaHound is *not* the best choice — pick the right tool

- **You want the fastest possible entry for barcoded discs and a slick mobile app** → **CLZ Movies**
  or **Libib** (Libib's free tier handles 5,000 items). Barcode scanning is near-instant and ~98%
  accurate for known UPCs; MediaHound's photo identification is broader but needs a quick review pass.
- **You also lend items / run a mini-library** (patrons, checkouts) → **Libib Pro**.
- **You want a mature OSS desktop database and don't need a shareable website** → **Tellico** (Linux/
  KDE, actively maintained) or **Data Crow** (cross-platform Java, self-hosted live web).
- **You're cataloging digital video files you own** → **Jellyfin** (FOSS) or **Plex**.
- **You want a fully custom schema and manual entry is fine** → **Notion / Airtable**.

## Honest limitations of MediaHound today

- **No barcode scanning** (by design — it uses photos), so for a pile of modern barcoded DVDs, a
  barcode app is faster.
- **No native mobile app** — it's a CLI plus a website (the website is mobile-responsive).
- **Identification needs review** — OCR/AI can misread a cover; MediaHound flags low-confidence ones for
  manual fix, but it's not the near-100% of a barcode lookup for known discs.
- **Younger and smaller** than CLZ/Libib, leaning on free public sources (Wikidata/OMDb/TMDB,
  MusicBrainz/Discogs, Open Library, LibriVox) rather than a single curated commercial database.
- **Editing is rebuild-based**, not a always-live app (edits export to JSON and apply on the next build).

If accuracy from photos, owning your data, a free modern website, and VHS support matter more than
barcode speed and a polished mobile app, MediaHound is built exactly for you.

## Sources

CLZ ([clz.com/movies](https://clz.com/movies)), Libib ([libib.com/pricing](https://www.libib.com/pricing)),
My Movies ([mymovies.dk](https://www.mymovies.dk/home/product-pricing.aspx)),
DVD Profiler ([invelos.com](http://www.invelos.com/), [Wikipedia](https://en.wikipedia.org/wiki/DVD_Profiler)),
GCstar ([gitlab.com/GCstar](https://gitlab.com/GCstar/GCstar)),
Tellico ([tellico-project.org](https://tellico-project.org/)),
Griffith ([archived repo](https://github.com/FiloSottile/Griffith)),
Data Crow ([datacrow.org](https://datacrow.org/news/)),
Plex ([plex.tv/plans](https://www.plex.tv/plans/)), Jellyfin ([jellyfin.org](https://jellyfin.org/)),
Notion/Airtable templates ([Airtable barcode](https://support.airtable.com/docs/using-the-barcode-field-in-airtable)).
