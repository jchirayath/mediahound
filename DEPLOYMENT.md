# Deploying a MediaHound site

A built site (e.g. `mysite/`) is **plain static files** — `index.html`, `identify.html`, `assets/`,
`data/`, `posters/`, `originals/`. Host it on anything that serves static files.

Build it first:

```bash
mediahound build --config mysite/config.toml          # offline rebuild
# (or --online to identify/enrich, see the README)
```

> The site also works by **double-clicking `index.html`** — the catalog is embedded in
> `data/bundle.js`, so no server is required for local viewing.

---

## Free hosting options

MediaHound output is **plain static files**, so it runs on every free static host. All of these
have a free tier that's plenty for a personal catalog:

| Host | Free tier | How |
|---|---|---|
| **GitHub Pages** | Unlimited public sites | commit the site folder, enable Pages (this repo's own demo runs here) |
| **Cloudflare Pages** | Unlimited sites & bandwidth | `npx wrangler pages deploy mysite` |
| **Netlify** | 100 GB/mo bandwidth | `npx netlify deploy --prod` or drag-and-drop |
| **Vercel** | Hobby tier | `vercel --prod` |
| **Render** | Free static sites | connect the repo, publish dir = your site folder |
| **Surge.sh** | Unlimited free sites | `npx surge mysite` |
| **Neocities / Bunny / S3 + CloudFront** | Free / pay-per-use | upload the folder |

Pick any one — there's no server, database, or build step to pay for. Details for the common ones below.

---

## Cloudflare Pages (free, generous)

```bash
cd mysite
npx wrangler pages deploy . --project-name my-movie-catalog
```

Or connect your GitHub repo in the Cloudflare dashboard (Pages → Create → Connect to Git), set the
**build output directory** to your site folder and leave the build command empty.

## Surge.sh (free, one command)

```bash
cd mysite
npx surge .            # pick a free *.surge.sh domain (or bring your own)
```

---

## Netlify (easiest)

```bash
cd mysite
npx netlify deploy --prod        # follow the prompt to create/link a site; publish dir = .
```

Or drag-and-drop the `mysite/` folder onto https://app.netlify.com/drop. A `netlify.toml`
(`publish = "."`, no build command) is created by `mediahound init`. To use a custom domain,
add it in **Site settings → Domain management** and point your DNS at Netlify.

## Vercel

```bash
cd mysite
vercel --prod        # framework: "Other"; output dir: .
```

## GitHub Pages

Commit the **site folder** (not your `.env`) to a repo and enable Pages:

```bash
cd mysite
git init && git add -A && git commit -m "Publish catalog"
gh repo create my-movie-site --public --source=. --push
gh api -X POST repos/<you>/my-movie-site/pages -f "source[branch]=main" -f "source[path]=/"
```

Then open `https://<you>.github.io/my-movie-site/`. (Paths in MediaHound are relative, so a project
subpath works.)

## Amazon S3 + CloudFront

```bash
aws s3 sync mysite/ s3://my-movie-bucket/ --delete
# enable static website hosting on the bucket (index document: index.html),
# or front it with CloudFront for HTTPS + a custom domain.
```

## Any web server (nginx / Apache / Caddy)

Copy `mysite/` to the web root and serve it. No special config needed — it's static. Example
(Caddy):

```
movies.example.com {
    root * /var/www/mysite
    file_server
}
```

---

## What to publish vs keep private

**Publish** (the site): `index.html`, `identify.html`, `assets/`, `data/*.json`, `posters/`, `originals/`.

**Never publish**: `config.toml` and `.env` (your provider keys + admin password plaintext).
Only the password **hash** is written into `data/site.json`, which is safe to ship. If you commit
your site folder to git, add `.env` and `config.toml` to its `.gitignore` (a `mediahound init` site
keeps them out of `web/` already; just don't add them by hand).

## Updating a deployed site

1. Add new photos to `RawImages/` (and/or drop exported `corrections.json` / `seen-overrides.json` /
   `identify-queue.json` into `data/`).
2. `mediahound build --config mysite/config.toml` (add `--online` to look up new titles).
3. Re-deploy with the same command you used above.
