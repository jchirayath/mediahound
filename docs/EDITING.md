# Editing & curating your catalog

This guide covers how to fix titles, mark items seen, manage photos, and — most importantly —
how to make those edits **stick** so they survive every future `mediahound build`.

## Bulk-importing a list of titles

To add many titles at once from a CSV (no photos needed):

- **CLI:** `mediahound import yourlist.csv` (add `--online` to fetch cover art & fill blanks).
- **Admin screen:** under `mediahound serve --admin`, click **⬆ Import list**, then paste or upload
  the CSV (and optionally tick *enrich online*).

**Only `title` is required.** The importer is tolerant of partial data: missing columns are left
blank or — with online enrichment — filled from the provider; unknown columns are ignored; headers
are case-insensitive; `media_type` is inferred (`music` if an `artist` is present, else `movie`).
So a one-column list of titles works, and so does a fully-specified sheet. See
[`examples/sample-import.csv`](../examples/sample-import.csv) for the recognised columns.

## How edits are stored

Every change you make in the **admin view** is recorded as a small **correction**, keyed by the
title's id, in:

```
data/
  corrections.json     ← title / year / format / studio / delete / rotate / set-default / re-query
  seen-overrides.json  ← which titles are marked seen (and when)
  view-config.json     ← library name, logo, visible fields, default columns
```

`mediahound build` regenerates the catalog (`collection.json`) from your photos **plus these
files**. So **`data/corrections.json` is the source of truth** for your manual fixes.

> ⚠️ **The #1 gotcha:** if you fix a title in the browser but it never reaches
> `data/corrections.json`, it shows locally but **reverts on the next build** — because the build
> rebuilds the catalog from `data/`. The two workflows below make sure your edits land in that file.

---

## Option A — Live admin server (recommended)

Zero manual steps: edits are written to `data/` *as you make them*.

```bash
mediahound serve --admin
# → http://127.0.0.1:8765   [ADMIN — saving to disk]
```

1. The site opens in your browser. Click **🔒 Admin** and enter your admin password.
2. Edit titles, years, formats; mark seen; rotate / set-default / delete photos.
   Each change shows a **“✓ Saved to disk”** badge — it's already in `data/corrections.json`.
3. Click **↻ Rebuild** to re-bake the catalog and reload (or just run `mediahound build` later).

Because the edit is already persisted, **it survives every future build and re-query** — this is the
fix for "my manual title rename reverted."

### Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `--admin` | off | Enable the write API (edits persist to `data/`). Without it, `serve` is a read-only preview. |
| `--port N` | `8765` | Port to listen on. |
| `--host H` | `127.0.0.1` | Bind address. **Keep it on localhost** — the write API is for you, not the public. |
| `--no-open` | off | Don't auto-open a browser. |
| `--config` | `config.toml` | Path to the site config. |

### Security

The write API is **bound to `127.0.0.1`** and **refuses cross-origin requests** (the `Origin` must
match the server). It's a local authoring tool — **never expose `--admin` on a public address or
reverse-proxy it to the internet.** Public hosting should always serve the plain static files
(Option B). The portal's admin password still gates the editing UI itself.

### Endpoints (for reference)

| Method & path | Body | Effect |
| --- | --- | --- |
| `GET /api/ping` | — | `{ok, admin, version}` — the portal uses this to detect server-admin mode |
| `POST /api/corrections` | `{ id: {patch}, … }` | merge into `data/corrections.json` |
| `POST /api/seen` | `{ id: {seen,date_seen}, … }` | replace `data/seen-overrides.json` |
| `POST /api/identify` | `{ hash: {title,…}, … }` | merge into `data/identify-queue.json` |
| `POST /api/rebuild` | `{}` | run an offline `build` and regenerate the site |

---

## Option B — Static export (for CDN / read-only hosting)

If you host the site as plain files (Netlify, GitHub Pages, S3…), there's no server to write to, so
edits live in your browser until you export them:

1. In admin view, make your edits.
2. Click **Export changes** (titles/formats/deletes…) and **Export seen** (watch state).
   The download is **merged with the site's existing `data/corrections.json`**, so it can never drop
   a previously-saved fix.
3. Move the downloaded `corrections.json` / `seen-overrides.json` into the site's `data/` folder.
4. Run `mediahound build` and redeploy.

---

## Moving a title between Movies and Music

Sometimes a disc is catalogued under the wrong type — e.g. a concert DVD that's really a
**music** release, or a spoken-word CD that belongs under **movies**. To move it:

1. In admin view, click the title to open the inline editor.
2. Change the **🎬 Movie / 🎵 Music** dropdown.
   - Switching to **Music** reveals an **Artist** field; the format list changes to CD / Vinyl /
     Cassette.
   - Switching to **Movie** shows the Studio / Distributor fields and DVD / VHS / … formats.
3. **Re-query** is auto-ticked when you change the type — so the next `mediahound build --online`
   re-enriches the item with the **correct provider** (MusicBrainz + Cover Art Archive for music,
   TMDB / Wikidata / OMDb for movies): artist, label, tracklist & cover art, or director, cast & poster.
4. Save. The card immediately moves to the right tab; the change persists like any other correction
   (via `serve --admin` or **Export changes**).

Behind the scenes the move sets a `media_type` correction and **clears the previous type's
exclusive fields** (a movie's director/cast/studio, or a music item's artist/label/tracklist) so the
record stays clean. Until you run an online re-query, music-specific fields stay empty.

On the next `mediahound build` (e.g. **↻ Rebuild** under `serve --admin`), the move also **relocates
the source cover photo** into the matching `RawImages/` subfolder (`video/` for movies, `audio/` for
music) so the item is correct *at the source* too — it won't snap back to the old type even if
`corrections.json` is ever cleared. This is idempotent (a photo already in place is left alone) and
only ever moves files **inside** `RawImages/`.

## Re-query vs. manual title

- A **manual title** you set always wins and is kept verbatim.
- Ticking **“re-query”** on an item asks the next `--online` build to refetch metadata for it. A
  re-query only replaces your title if the result is a *plausible* match; otherwise your title is
  kept. To freeze a title so nothing ever changes it, set it manually and leave re-query **off**.

## Recovering edits that already reverted

If titles you fixed reverted on a rebuild, they were never saved to `data/corrections.json`. If the
edits are **still in the browser** where you made them, open that browser, go to admin view, and
click **Export changes** — the merge-safe export captures everything still in `localStorage`. Drop it
into `data/`, rebuild, and they're permanent. Going forward, use `serve --admin` to avoid the manual
step entirely.
