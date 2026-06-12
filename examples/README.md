# Examples

The fastest way to see MediaHound without any photos or API keys:

```bash
mediahound init demo
mediahound build --config demo/config.toml --mock
cd demo && python3 -m http.server 8080
```

`--mock` writes a small sample catalog spanning all five media types — 🎬 movies, 🎵 music, 📚 books,
🎮 video games and 🎧 audiobooks — plus one "unidentified" item, with **real demo cover art**
(hotlinked: Open Library for books/audiobooks, Steam capsules for games). So every part of the UI —
the per-type tabs, search, filters, sorting, the detail modal, music tracklists/song search,
mark-as-seen, the export round-trips, and the identify page — is demoable offline.

To try the real **zero-key** pipeline, drop a few cover photos into `demo/RawImages/` and run
`mediahound build --config demo/config.toml` (uses Tesseract OCR + Wikidata / MusicBrainz / Open
Library / LibriVox, depending on media type).

## Importing a sample list (CSV)

[`sample-import.csv`](sample-import.csv) shows the recognised columns with one row per media type
(movie / music / book / game / audiobook). Only `title` is required; `media_type` is inferred from
the columns present (e.g. an `author` → book/audiobook, a `developer`/`platforms` → game) or set it
explicitly. Try it with:

```bash
mediahound import examples/sample-import.csv --config demo/config.toml --online
```

Type-specific columns include `author`, `narrator`, `developer`, `publisher`, `platforms`,
`tracklist`, `isbn`, `pages`, and `duration`.

## Printable inventory (PDF)

`mediahound export --format inventory --config demo/config.toml` writes a self-contained, print-ready
`inventory.html` grouped by media type with per-type and grand-total estimated value; open it and use
the browser's **Print → Save as PDF** (zero dependencies). The web admin's Export menu has the same
"🖨 Printable inventory (PDF)" action.
