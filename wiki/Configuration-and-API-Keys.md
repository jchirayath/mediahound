# Configuration & API keys

MediaHound works **zero-key by default** (Tesseract OCR + Wikidata for movies, MusicBrainz + Cover Art
Archive for music). API keys are optional and only make metadata/posters richer.

## config.toml

`mediahound init` scaffolds `config.toml`. It picks the identify/metadata providers and paths. The
defaults are offline-friendly; edit it to opt into online providers. See
[`config.example.toml`](https://github.com/jchirayath/mediahound/blob/main/mediahound/config.example.toml).

## 🔑 API keys (optional)

Providers that need a key: **TMDB** and **OMDb** (movie metadata/posters) and **Anthropic** (Claude
vision identification).

### Set them in the admin console (recommended)

**⚙ Settings → API keys** → paste a key → **Save**.

- Stored in your computer's **OS keychain** (macOS Keychain / Windows Credential Manager / Linux
  Secret Service) — **never written to a file**, never shown back to the browser (the panel only shows
  *✓ set / not set*).
- The build reads them automatically. After saving, run **↻ Rebuild** with online enabled
  (or `mediahound build --online`).
- For security this panel is **localhost-only** — hidden and refused over `--phone`/LAN mode, so keys
  never travel the network.

### Or use a .env file

Prefer files? Put them in a **gitignored `.env`** next to `config.toml`:

```
TMDB_API_KEY=…
OMDB_API_KEY=…
ANTHROPIC_API_KEY=…
```

**Precedence:** real environment variables → `.env` → the OS keychain.

## Where to get keys

- **TMDB** — https://www.themoviedb.org/settings/api (free)
- **OMDb** — http://www.omdbapi.com/apikey.aspx (free tier)
- **Anthropic** — https://console.anthropic.com/ (paid; only if you use Claude vision)

Secrets never get committed to the repo — only the admin-password **hash** ships in `site.json`.
