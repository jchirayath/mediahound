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
| Claude identification | The cover **image** is sent to the Anthropic API — only if you opt into the `claude` identifier. |
| 🌐 **Publish** | The **generated static site** is uploaded to **Netlify** using your token. Your source photos, `.env`, and `config.toml` are **never** included. |
| 📱 **Phone upload** (`app --phone`) | Photos travel **only over your local Wi-Fi**, protected by a per-session token — never to the internet. |
| Clicking a "watch / listen / more info / sell" link | A normal outbound link to that third-party website. |

A default build is **offline** and makes **no network calls at all**.

## Third parties

When you enable online features, your queries are subject to the privacy policies of those services
(TMDB, OMDb, Wikidata, MusicBrainz, JustWatch, Anthropic, Netlify). MediaHound sends only what's
needed to identify/enrich a title or deploy your site, and never shares data between them.

## Publishing is public

A published catalog is a public website — anyone with the link can view it. It includes your titles,
cover art, and any notes you added, but **not** your source photos, keys, or config. Don't publish
anything you would not want to be public.

## Your controls

- **Stay fully offline:** don't pass `--online` and don't Publish.
- **Remove stored keys:** clear them in **Settings → API keys**, or from your OS keychain.
- **Delete everything:** remove your library folder. A published site is removed from your Netlify
  dashboard.

## Children's privacy & scope

MediaHound is a local tool, not an online service; it collects nothing about anyone. Questions or
concerns: open an issue at <https://github.com/jchirayath/mediahound/issues>.

See also [SECURITY.md](SECURITY.md).
