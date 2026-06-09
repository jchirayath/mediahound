# Security

ReelShelf builds a **static website** — there is no server, database, or backend at runtime. That
shapes the whole threat model: a published catalog is **read-only to everyone**, and there's no
live service to attack, no session to hijack, and no server-side data to leak.

## Reporting a vulnerability

Please open a [GitHub Security Advisory](https://github.com/jchirayath/reelshelf/security/advisories/new)
(preferred) or a regular issue. We'll respond as quickly as we can.

## The admin password is a convenience gate, **not** an access-control boundary

The "Admin" view is unlocked by comparing `SHA-256(typed password)` against a hash published in the
site (`data/site.json`). Understand what this does and doesn't protect:

- **It does not protect the published catalog.** Admin mode only enables *client-side* editing tools
  whose changes are saved to the visitor's **own browser** (`localStorage`) and can be *exported* as
  JSON. Nothing a visitor does in admin mode affects the live site or anyone else. Changing the
  published catalog requires running `reelshelf build` and re-deploying — i.e. access to your repo /
  host, which is the real security boundary.
- **The hash is public and unsalted**, so it is brute-forceable. Therefore:
  - Use a **strong, unique** admin password that you don't reuse anywhere else.
  - Treat admin as "keep casual visitors out of the editing UI", not as authentication.
- A determined user can bypass the gate via dev-tools regardless of the password — and still only
  affects their own local view. That's by design for a static site.

## Secrets

- API keys (Anthropic, TMDB, OMDb) are read **only** from a gitignored `.env` next to `config.toml`.
  They are never written into the generated site and never committed.
- Only the admin password **hash** is published (in `site.json`) — never the plaintext.
- `.env`, `config.toml`, `data/`, `posters/`, `originals/`, and `RawImages/` are gitignored. Don't
  add them by hand to a published repo.
- CI / the demo build runs with `--mock` (offline) and uses **no keys**.

## Cross-site scripting (XSS)

- All catalog data (titles, cast, overview from third-party providers or your edits) is rendered
  **HTML-escaped**.
- Links (`where to watch`, `sell`, logo) are restricted to `http(s)` or site-relative URLs — a
  `javascript:` / `data:` URL from a provider response or imported file is neutralised.
- The library name/description are set via `textContent`; the logo is an `<img>` (SVG scripts in
  `<img>` don't execute).

## Imported files are trusted owner input

`corrections.json`, `seen-overrides.json`, and `identify-queue.json` are produced by the admin UI and
re-applied at build time. Only apply files **you** generated. As defense-in-depth the build:

- restricts photo **rotation** to image files inside the site's own `posters/` / `originals/`
  folders (rejects `../` path-traversal), and
- treats edits as data only (no code is ever executed from these files).

## Build-time network

- Online lookups happen only with `--online`; the default build is fully offline.
- Metadata providers are reputable third parties (TMDB / OMDb / Wikidata / JustWatch). Poster
  downloads are restricted to `http(s)`. The build runs on your own machine, so treat providers as
  semi-trusted; if you build untrusted catalogs at scale, run it in a sandbox.

## Dependencies

Runtime deps are `requests`, `Pillow`, and (optional) `pytesseract`. **Image parsing relies on
Pillow** — keep it updated, since image libraries are a common source of CVEs. `pip install -U
Pillow` periodically, or pin a known-good version.

## Hosting

The output is static files; any static host (GitHub Pages, Cloudflare/Netlify/Vercel, S3) is fine.
Serve over **HTTPS** (all the suggested hosts do by default). There is no server-side attack surface
to harden beyond that.
