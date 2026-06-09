# Deploying a ReelShelf site

A built site (e.g. `mysite/`) is **plain static files** — `index.html`, `identify.html`, `assets/`,
`data/`, `posters/`, `originals/`. Host it on anything that serves static files.

Build it first:

```bash
reelshelf build --config mysite/config.toml          # offline rebuild
# (or --online to identify/enrich, see the README)
```

> The site also works by **double-clicking `index.html`** — the catalog is embedded in
> `data/bundle.js`, so no server is required for local viewing.

---

## Netlify (easiest)

```bash
cd mysite
npx netlify deploy --prod        # follow the prompt to create/link a site; publish dir = .
```

Or drag-and-drop the `mysite/` folder onto https://app.netlify.com/drop. A `netlify.toml`
(`publish = "."`, no build command) is created by `reelshelf init`. To use a custom domain,
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

Then open `https://<you>.github.io/my-movie-site/`. (Paths in ReelShelf are relative, so a project
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
your site folder to git, add `.env` and `config.toml` to its `.gitignore` (a `reelshelf init` site
keeps them out of `web/` already; just don't add them by hand).

## Updating a deployed site

1. Add new photos to `RawImages/` (and/or drop exported `corrections.json` / `seen-overrides.json` /
   `identify-queue.json` into `data/`).
2. `reelshelf build --config mysite/config.toml` (add `--online` to look up new titles).
3. Re-deploy with the same command you used above.
