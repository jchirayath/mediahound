# Privacy

MediaHound is built to keep your collection **yours**. It's offline-first and local by default — there
is no MediaHound account, no telemetry, and no server we run that sees your data.

> Canonical copy: [PRIVACY.md](https://github.com/jchirayath/mediahound/blob/main/PRIVACY.md).

## What stays on your computer (everything, by default)

- Your **cover photos**, the generated **catalog**, your **edits**, and your **library** all live in
  the folder you chose (or `~/MediaHound Library`). Nothing is uploaded anywhere unless *you* do it.
- **No analytics, no telemetry, no phone-home.** The app never reports usage.
- **API keys** are stored in your **OS keychain** (or a gitignored `.env`) — never in a file we ship,
  never sent to the browser. The admin write API is **localhost-only**.

## When data leaves your computer — only because you asked

| Action | What's sent, and to whom |
| --- | --- |
| `build --online` | Title/artist queries to the metadata providers you enabled (TMDB, OMDb, Wikidata, MusicBrainz, JustWatch). Standard web API calls. |
| Claude identification | The cover image is sent to the Anthropic API (only if you enable the `claude` identifier). |
| 🌐 **Publish** | The **generated site** is uploaded to **Netlify** with your token. Source photos, `.env`, and `config.toml` are **never** included. |
| 📱 **Phone upload** | Photos travel **only over your local Wi-Fi**, token-protected — never to the internet. |
| Clicking a "watch / listen / sell" link | A normal outbound link to that third-party site. |

Default builds are **offline** and make **no network calls at all**.

## Publishing is public

A published catalog is a public website — anyone with the link can see it. It contains your titles,
cover art, and any notes you added, but **not** your source photos, keys, or config. Don't publish
anything you wouldn't want public.

## Your controls

- Stay fully offline: just don't pass `--online` and don't Publish.
- Delete everything: remove your library folder. Remove stored keys in **Settings → API keys** (or
  your keychain). A published site is deleted from your Netlify dashboard.

See also: **[[Configuration and API Keys]]**, **[[Publishing Your Catalog]]**, and
[SECURITY.md](https://github.com/jchirayath/mediahound/blob/main/SECURITY.md).
