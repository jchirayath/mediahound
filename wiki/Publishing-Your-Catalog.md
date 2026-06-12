# Publishing your catalog

Your catalog is a **static website** (`mysite/` — `index.html` + `assets/` + `data/` + posters), so
you can host it anywhere. Your source photos and config never need to leave your computer.

## 🌐 One-click Publish (Netlify)

In the admin console, click **🌐 Publish**. The first time, paste a **Netlify access token**
(netlify.com → User settings → Applications → New access token) — it's stored in your OS keychain.
MediaHound deploys the site and hands you a shareable link.

- The site id is remembered (in `data/.netlify-site.json`), so the URL stays stable across publishes.
- Only the generated site is uploaded — `RawImages/`, `.env`, `config.toml` and dotfiles are excluded.
- Publish is **localhost-only** (it uses your token), so it's disabled in `--phone`/LAN mode.

## Other static hosts

Deploy the site folder to any static host:

- **Netlify / Vercel / Cloudflare Pages / GitHub Pages / S3** — drag the folder in, or point the host
  at it. A `netlify.toml` is scaffolded for you.
- The site works from `file://` too (it embeds `data/bundle.js`), so you can just open `index.html`.

## 📱 Install it on your phone (PWA)

A published catalog is a **Progressive Web App**: open it in your phone's browser and choose
**Add to Home Screen** — you get an app icon, a full-screen view, and offline access (the catalog is
cached). It **auto-updates** whenever you republish. This is read-only browsing; editing still happens
in the local app (`mediahound app`) and is then published.

## ⚠️ Never expose the admin server publicly

`serve --admin` / `app` / `gui` run a **localhost-only write API** for authoring. Public hosting
should always serve the **plain static files** (Option B above) — never reverse-proxy the admin server
to the internet. The portal's admin password is a convenience gate, not server-side auth. See
[SECURITY.md](https://github.com/jchirayath/mediahound/blob/main/SECURITY.md).
