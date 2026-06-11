# 04 — Personal catalog

**Status:** Planned · **Effort:** S–M · **Depends on:** nothing (frontend + override files)

Turn the inventory into a **personal** catalog: your ratings, notes, shelves/tags, who you've lent
things to, and a "surprise me" picker. Almost all of this extends the existing override-file +
admin-write-API + frontend patterns, so edits **persist to `data/` and survive every rebuild**.

## Why

People don't just want a list of what they own — they want *their* take on it, ways to organize it,
and help deciding what to use tonight. These are the features that make someone open the app weekly.

## Features & data model

All new personal data is **admin-only** (see *Privacy* below).

| Feature | Storage | Notes |
|---|---|---|
| **Personal rating** (★ 1–10) | `corrections.json` → `my_rating` | distinct from the provider rating; sortable |
| **Personal notes** | `corrections.json` → `my_note` | free text per item |
| **Tags / shelves** | `corrections.json` → `tags: []` | user-defined groupings ("Christmas", "to sell", "Dad's vinyl") |
| **Lending** | new `data/loans.json` (id → `{to, since, returned}`) | separate file, like `seen-overrides.json` |

Keeping ratings/notes/tags in `corrections.json` reuses `/api/corrections` (merge-on-write, already
rebuild-safe). Loans get their own file + `POST /api/loans` (mirrors `/api/seen`).

## UX

- **Inline editor:** a ★ rating control, a notes textarea, and a tag input (chips).
- **Loan:** a "Loan out" button → who + date; a **badge** on loaned cards; a filter **On loan /
  Available**; a "Who has my stuff?" view listing everything currently out.
- **Shelves:** a tag filter + chips; optionally a left rail of shelves.
- **"🎲 Surprise me":** picks a random item from the current filter (default: **unseen**), with optional
  constraints (runtime ≤ N, genre, media type). Pure client-side — no data change. High delight, ~30 lines.
- **Sort additions:** by my-rating, by recently-rated.

## Architecture

- **Frontend (`app.js`)** does most of the work: new inputs in the inline editor, new filters/sorts,
  the surprise-me button, loan dialog + badges. Writes go through the existing `persist()` →
  `/api/corrections` (and a new `/api/loans`).
- **`serve.py`:** add `/api/loans` (merge/replace like `/api/seen`).
- **`pipeline.py` / `store.py`:** apply `my_rating` / `my_note` / `tags` from corrections (like other
  correction fields); load `loans.json` for the admin view.

## Privacy (important)

Ratings, notes, tags, and **especially loans** are personal and must **not** appear in a published
public catalog. They render **only in the admin view** and are **stripped from the public
`bundle.js` / `collection.json`** at build (a new "private fields" filter in `_write_site`). This is a
deliberate extension of the PRIVACY.md "publishing is public" rule.

## Phasing

1. **P1** — **personal ratings + notes** and **🎲 Surprise me** (low effort, immediate delight).
2. **P2** — **tags / shelves** + tag filter.
3. **P3** — **lending tracker** (loans.json, badges, "who has my stuff").

## Testing

- Corrections round-trip for `my_rating`/`my_note`/`tags`; `/api/loans` persistence.
- **Privacy test:** a published build's `collection.json`/`bundle.js` contains **no** `my_note` /
  `loans` data, while the admin view does.

## Open questions

- Should tags be sharable on a *published* site (public shelves) as an opt-in? Default: private.
- Loan reminders (e.g., "out for 90 days") — a nice nudge, but needs a notification surface; defer.
