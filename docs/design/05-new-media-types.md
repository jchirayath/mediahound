# 05 — New media types: Books & Video games

**Status:** 📚 Books **shipped** (P1) · 🎮 Games planned · **Effort:** L · **Depends on:** Barcode (01)

> **P1 shipped.** Books are implemented: Open Library provider (`metadata/openlibrary.py`), ISBN
> auto-routing (978/979), `📚 Books` tab + card + editor, `RawImages/books/`, CSV import/export, and
> `_MOCK_BOOKS`. The movie/music field-clearing was generalised to N types. Video games (P3) remain
> designed below. The full media-type *registry* refactor is deferred — books were added by extending
> the existing movie/music pattern; the registry is the recommended cleanup before a 5th type.

## Why

MediaHound already catalogs **movies** and **music** from cover photos / barcodes. The same pipeline —
identify → enrich → value → catalog → publish — applies cleanly to two more shelf-dwelling collectibles:

- **📚 Books.** Every book has an **ISBN barcode** (EAN-13, the `978`/`979` "Bookland" prefix). That's an
  *exact* identifier, just like a music barcode — and **Open Library** resolves it to title/author/cover
  with **no API key** (matching our zero-key default). Big new audience, almost no new infrastructure.
- **🎮 Video games.** Boxes carry a **UPC**; the resale market (especially retro) is *strong*, which leans
  straight into MediaHound's resale/value identity. Covered by **Wikidata** (zero-key) for the default and
  **IGDB / RAWG** for richer data.

Doing **both at once** is deliberate: it forces us to stop hard-coding `movie` vs `music` and instead
introduce a **media-type registry** — after which a 5th type (comics, board games, vinyl toys…) is *data,
not code*. The brand already nods this way: the logo is a hound in a **TV over an open book**, and the name
"MediaHound" is media-agnostic.

## The core idea — a media-type registry

Today the two types are encoded as scattered `if media_type == "music"` branches (≈50 in Python, plus
`isMusic(m)` / `FORMATS_BY_TYPE` / media-tabs in the frontend). Adding two more types by extending those
branches is how software rots. Instead, describe each type **once**, in a registry both layers read:

```python
# mediahound/mediatypes.py  (new — single source of truth)
TYPES = {
  "movie": Type(label="Movies",  emoji="🎬", folder="video",
                creator=("director","🎬"), org=("studio","🏛"),
                dimension=("format","Format", ["DVD","VHS","Blu-ray","VideoCD","Unknown"]),
                meta_fields=["rating","format","runtime","language"],
                provider="movie", links="watch"),
  "music": Type(label="Music",   emoji="🎵", folder="audio",
                creator=("artist","🎤"), org=("label","🏷"),
                dimension=("format","Format", ["CD","Vinyl","Cassette","Unknown"]),
                meta_fields=["rating","format","tracks"], provider="music", links="listen"),
  "book":  Type(label="Books",   emoji="📚", folder="books",
                creator=("author","🖊"), org=("publisher","🏢"),
                dimension=("format","Format", ["Hardcover","Paperback","Mass Market","eBook","Audiobook","Unknown"]),
                meta_fields=["rating","format","pages","language"], provider="book", links="read"),
  "game":  Type(label="Games",   emoji="🎮", folder="games",
                creator=("developer","🕹"), org=("publisher","🏢"),
                dimension=("platform","Platform", ["Switch","PS5","PS4","Xbox","PC","Retro","Unknown"]),
                meta_fields=["rating","platform","players"], provider="game", links="play"),
}
```

The frontend ships a mirror of this as a JS object. Every per-type decision (folder routing, which fields a
card shows, the editor's format list, the "creator/org" labels, which provider to call, what the secondary
links are) becomes a **registry lookup**. The existing movie/music behaviour is preserved by making them the
first two entries.

> Note the **`format` field is reused as the type's primary dimension** — for games it carries the
> **platform** and the UI labels it "Platform". No schema change, just a per-type label.

## How identification works (reuse the pipeline)

```
barcode (scan or photo decode)
   │  EAN-13 / UPC
   ▼
 route by prefix + the user's media tab
   ├─ 978/979  → BOOK   → Open Library /isbn/{isbn}      (exact, free)
   ├─ UPC + 🎮  → GAME   → UPCItemDB → product name → game identify-by-title
   └─ UPC + 🎬/🎵 → existing movie/music paths
OCR / Claude fallback → title (+ author / platform) → metadata provider
```

- **Books are the sweet spot:** the ISBN prefix (`978`/`979`) is self-identifying, so a scanned book needs
  **no media-type choice** — we can auto-route it. (Movies, music and games all use generic UPCs and are not
  distinguishable by barcode alone, so the scan UI keeps a type selector — now four options.)
- Games reuse the **movie-style UPC → product-name → identify-by-title** path (UPCItemDB already exists).

## Metadata providers

| Type | Default (zero-key) | Richer (optional key) | Cover art | Resale "Discogs equivalent" |
|---|---|---|---|---|
| Book | **Open Library** (`openlibrary.org`, CC0) | Google Books | covers.openlibrary.org | (used-book market is thin) |
| Game | **Wikidata** (reuse `WikidataProvider`) | **IGDB** (Twitch OAuth) / **RAWG** (free key) | IGDB/RAWG art | **PriceCharting** (retro price guide) |

New: `metadata/openlibrary.py` → `BookMeta`; `metadata/igdb.py` (or extend Wikidata) → `GameMeta`. Both
implement the existing `MetadataProvider` shape and are selected by `get_metadata_provider(cfg, "book"|"game")`.

## Data model

`media_type` gains `"book"` and `"game"`. New per-type fields on an item (all optional, override-safe):

- **Book:** `author`, `publisher`, `year`, `page_count`, `isbn`, `subjects[]` (→ genres), `series`.
- **Game:** `developer`, `publisher`, `year`, `platform` (in `format`), `players`, `esrb`, `genres[]`.

Stored the same way as movie/music fields and settable via `corrections.json` (rebuild-safe). No migration —
existing catalogs are untouched; books/games are purely additive.

## Companion imports (high synergy)

- **Goodreads CSV → books.** Goodreads exports your library as CSV (ISBN, title, author, **My Rating**,
  **Bookshelves**, Date Read). That maps *directly* onto our model — **rating → `my_rating`, shelves →
  `tags`, read → seen** — pairing beautifully with the shipped personal catalog. A natural sibling to the
  Discogs and Letterboxd flows.
- **PriceCharting → games** for resale, the way Discogs prices music.

## Implications & side-effects (what this touches)

**Backend (~50 branch points + new modules):**
- `mediatypes.py` (new registry) — the de-risking move; everything else reads it.
- `store.py` — `MEDIA_FOLDERS` gains `books`→book, `games`→game; `_images_in` unchanged.
- `pipeline.py` — `_process_one` becomes a registry dispatch (vs the current movie/`_process_music` fork);
  new `_process_book`/`_process_game` (mirror `_process_music`); `_apply_corrections` field-clearing sets
  (`_MOVIE_ONLY`/`_MUSIC_ONLY` → derived from the registry); `_FORMATS` → registry; `_build_mock` gains
  `_MOCK_BOOKS`/`_MOCK_GAMES`; barcode-first pass adds the ISBN route.
- `metadata/` — `BookMeta`/`GameMeta` (or a generic `ItemMeta`), `openlibrary.py`, `igdb.py`;
  `get_metadata_provider` + `config.py` gain `[book.metadata]` / `[game.metadata]`.
- `barcode.py` — ISBN (978/979) auto-routes to books; game UPC → UPCItemDB path; `music_item_from_meta`
  generalizes to `item_from_meta`.
- `csvio.py` — the `media_type = "music" if artist else "movie"` heuristic **breaks** for books/games
  (author≠artist); rows now need an explicit `media_type`. `EXPORT_COLUMNS` += author/publisher/isbn/pages/platform.
- `resale.py` — `_BASE` baselines for book/game formats; eBay query unchanged (games resell *well* → a win).
- `cli.py` — `init` scaffolds `RawImages/books/` + `games/`; `import-discogs` gets siblings (`import-goodreads`).
- `links.py` — new `read_links` (Open Library / Goodreads / Libby) and `play_links` (where-to-play) helpers,
  alongside `listen_links`; `streaming.py` (JustWatch) stays movie-only.

**Frontend (the largest surface):**
- The binary `isMusic(m)` (used in card rendering, filters, the editor) becomes a **registry-driven**
  dispatch — the single biggest correctness risk if left as ad-hoc conditionals (a book would render as a
  movie, showing "director/studio/Where to watch"). Generalizing to the registry fixes this *and* future types.
- A third/fourth **media tab** (📚 Books, 🎮 Games); `mediaType` filter extends to `book`/`game`; tabs already
  auto-hide when only one type is present, so mixed/single catalogs both stay clean.
- `FORMATS_BY_TYPE` → registry; the editor's media-type `<select>` lists all types; the "creator/org" field
  labels (Director/Artist/Author/Developer · Studio/Label/Publisher) come from the registry.
- Search haystack += author/publisher/subjects/platform; filter dropdowns relabel ("All studios" →
  generic "All makers" or per-tab labels).
- Add-photos & Scan dialogs gain Book/Game options; the scan type selector grows to four (ISBN auto-routes).
- Letterboxd export stays movie-only; a **Goodreads-style export** is the natural book companion.

**Docs & brand:**
- The "**movies & music**" tagline appears across README / wiki / PRIVACY / `config.example` / the site
  subtitle / the `🎬🎵` emoji — a broad but mechanical text sweep to "movies, music, books & games."
- `manifest.json` description, the welcome screen, and the demo/mock all widen.

**Scale (worth flagging):** book libraries can be **thousands** of items. The grid renders every card; large
catalogs already stress this, and books amplify it — this is the point where **list virtualization /
pagination** likely graduates from "nice" to "needed" (a follow-on, not a blocker).

**What does *not* change:** the privacy model (personal data still stripped from published sites), the
override-file persistence, the admin write API, offline-first/zero-key defaults, and existing movie/music
catalogs (fully backward-compatible).

## Dependencies

- Books: none beyond `requests` (Open Library is keyless). Optional `GOOGLE_BOOKS_KEY`.
- Games: none for the Wikidata default; optional `IGDB`/`RAWG`/`PRICECHARTING` keys via the keychain
  (`keystore.py` allow-list + Settings → API keys).
- ISBN decoding reuses the existing `mediahound[barcode]` extra (EAN-13 already supported).

## Privacy / offline

Same posture: decoding is local; provider lookups are online and gated behind `--online` / explicit scan/
import. No accounts. New tokens live in the OS keychain. Goodreads/PriceCharting imports read *your* data only.

## Phasing

1. **P1 — the registry + Books.** Introduce `mediatypes.py` (refactor movie/music to read it, no behavior
   change), then add **books**: Open Library provider, ISBN auto-route, `RawImages/books/`, card/editor/tab,
   `_MOCK_BOOKS`. Ships the smaller, keyless type and de-risks everything after it.
2. **P2 — Goodreads import** (`import-goodreads`) → ratings/shelves/seen mapping.
3. **P3 — Video games.** Wikidata default + IGDB/RAWG optional; `RawImages/games/`; platform dimension;
   `_MOCK_GAMES`.
4. **P4 — PriceCharting** game resale; (optional) a books value/insights tie-in.

## Testing

- Registry: every type round-trips folder routing, format/dimension normalization, and a type-move that
  clears the *other* types' fields (extend the existing movie↔music move test to N-way).
- Open Library / IGDB: mocked JSON → `BookMeta`/`GameMeta`; ISBN 978/979 auto-routes to books; a game UPC
  routes through UPCItemDB.
- Goodreads CSV round-trip → ratings/shelves; privacy test still passes (personal fields stripped).

## Open questions

- **Generic `ItemMeta` vs. per-type dataclasses?** A registry argues for one flexible `ItemMeta`; weigh
  against the clarity of typed `MovieMeta`/`MusicMeta`/`BookMeta`/`GameMeta`.
- **Platform vs. format.** Reusing `format` for game platform is cheap but slightly leaky; a dedicated
  `platform` field is cleaner long-term. Same question lurks for book "edition."
- **IGDB auth** (Twitch OAuth client-id+secret) is heavier than a single API key — is RAWG (one free key) the
  better default "richer" game provider?
- **Scale**: do books push us to virtualize the grid now, or defer until a real large-library report?
