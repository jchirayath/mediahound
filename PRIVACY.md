# Privacy

MediaHound is built to keep your collection **yours**. It is offline-first and runs entirely on your
own computer. There is **no MediaHound account, no telemetry, and no server we operate that sees your
data.** This document explains exactly what is stored, and the only times anything leaves your machine.

## What stays local (everything, by default)

- Your **cover photos**, the generated **catalog**, your **edits**, and the whole **library** live in
  the folder you chose (or `~/MediaHound Library`). Nothing is uploaded anywhere unless you do it.
- **No analytics, no telemetry, no phone-home.** The app never reports usage or crashes to us.
- **API keys** are stored in your **OS keychain** (macOS Keychain / Windows Credential Manager / Linux
  Secret Service) or a gitignored `.env` — never in a file we ship, and never returned to the browser.
- The admin write API is bound to **`127.0.0.1`** (localhost only) and refuses cross-origin writes.
- The published repo never contains secrets — only the admin-password **hash** ships in `site.json`.

## When data leaves your computer — only because you asked

| Action | What is sent, and to whom |
| --- | --- |
| `mediahound build --online` | Title / artist lookups to the metadata providers you enabled: TMDB, OMDb, Wikidata, MusicBrainz / Cover Art Archive, and JustWatch (where-to-watch). Ordinary web API calls. |
| 📷 **Barcode lookup** (`--online` / Scan) | The decoded **UPC/EAN number** (not the photo) is sent to MusicBrainz/Discogs (music) or UPCItemDB (movies) to resolve the exact release/title. Decoding itself is local. |
| 💿 **Discogs** (`import-discogs`, price) | Reads *your* Discogs collection / a release's price suggestions using your token. Nothing is written back to Discogs. |
| Claude identification | The cover **image** is sent to the Anthropic API — only if you opt into the `claude` identifier. |
| 🌐 **Publish** | The **generated static site** is uploaded to **Netlify** using your token. Your source photos, `.env`, `config.toml`, your **personal data** (`corrections.json`, `loans.json`), and the **change log** (`events.jsonl`) are **never** included. |
| 🧾 **Change log** | `data/events.jsonl` is a local, append-only audit of adds/removes/changes (compact: integer timestamp, one-char op, **field names only** for changes — never their values). Admin-only; never published. View it with `mediahound log`. |
| ⬇ **Backup** | Writes a **local** zip of your library. Never uploaded; `.env`/secrets are excluded. |
| 📱 **Phone upload** (`app --phone`) | Photos travel **only over your local Wi-Fi**, protected by a per-session token — never to the internet. |
| Clicking a "watch / listen / more info / sell" link | A normal outbound link to that third-party website. |

A default build is **offline** and makes **no network calls at all**.

## Third parties

When you enable online features, your queries are subject to the privacy policies of those services
(TMDB, OMDb, Wikidata, MusicBrainz, JustWatch, Anthropic, Netlify). MediaHound sends only what's
needed to identify/enrich a title or deploy your site, and never shares data between them.

## Publishing is public

A published catalog is a public website — anyone with the link can view it. It includes your titles
and cover art, but **not** your source photos, keys, config, or **personal catalog data**. Your
personal **ratings, notes, tags/shelves, and lending records are admin-only** — they are stripped
from the published `collection.json` / `bundle.js`, and `corrections.json` / `loans.json` are never
uploaded. They render only in the local admin view. Don't publish anything you would not want public.

## Your controls

- **Stay fully offline:** don't pass `--online` and don't Publish.
- **Remove stored keys:** clear them in **Settings → API keys**, or from your OS keychain.
- **Delete everything:** remove your library folder. A published site is removed from your Netlify
  dashboard.

## Children's privacy & scope

MediaHound is a local tool, not an online service; it collects nothing about anyone. Questions or
concerns: open an issue at <https://github.com/jchirayath/mediahound/issues>.

See also [SECURITY.md](SECURITY.md).
