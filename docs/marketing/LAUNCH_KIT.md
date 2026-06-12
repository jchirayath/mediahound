# MediaHound launch kit

Ready-to-use copy for launching MediaHound. Edit names/links if anything moved.
Live demo: https://jchirayath.github.io/mediahound/ · Repo: https://github.com/jchirayath/mediahound · `pip install mediahound`

**Positioning (use everywhere):** the free, open-source, *private* way to turn a shelf of
movies, music, books, audiobooks and games into a searchable catalog you own — no account,
no subscription, no API keys, works offline.

**Three wedges** (lead with whichever fits the audience):
1. **Free & open-source** — vs. Libib (freemium/account) and CLZ/Data Crow (paid).
2. **Private & offline** — no account, runs locally, only goes online if you pass `--online`; output is a static site you own.
3. **One tool, every medium** — 🎬 movies · 🎵 music · 📚 books · 🎧 audiobooks · 🎮 games — via photo OCR, **barcode/ISBN/UPC scan**, or CSV.

---

## 1. Show HN

**Title** (≤80 chars, no emoji, factual — HN style):
```
Show HN: MediaHound – photos of your DVD/CD/book shelf to a searchable catalog
```
**URL:** https://jchirayath.github.io/mediahound/  (link the demo, not the repo — people click through)

**First comment (you, as maker) — post immediately after submitting:**
```
I kept buying DVDs/CDs/books I already owned, and every "collection manager" I tried
wanted an account and a subscription and put my catalog on their servers. So I built
MediaHound: point it at a folder of cover photos (or scan a barcode, or import a CSV)
and it identifies each item, pulls cover art + metadata, writes a short blurb, estimates
resale value, and generates a static searchable website you host anywhere.

Design choices that mattered to me:
- Zero API keys to start — open-source OCR + open data (MusicBrainz, Wikidata, Open
  Library). TMDB/OMDb keys are optional for richer movie data.
- Offline-first: it never hits the network unless you pass --online.
- Output is a plain static site (HTML/JS) — deploy to Netlify/Pages/S3 or just open the
  file. Your photos, keys, and catalog never touch my repo.
- One tool for movies, music, books, audiobooks, and games.

MIT-licensed, Python, and there are notarized macOS/Windows desktop builds if you don't
want a terminal. Demo (admin password `changeme`): https://jchirayath.github.io/mediahound/
Repo: https://github.com/jchirayath/mediahound — happy to answer anything.
```
**Timing:** Tue–Thu, ~8–10am US-Eastern. Stay in the thread for the first 2–3 hours and
reply to every comment. Don't ask for upvotes.

---

## 2. Reddit (one per week, tailored — do NOT cross-post identical text)

### r/selfhosted  —  lead with ownership/privacy
**Title:** `MediaHound – self-hosted, account-free catalog for your movies/music/books/games (static output)`
**Body:**
```
I wanted to catalog my physical media without handing it to a SaaS. MediaHound takes
photos of your shelf (or a barcode scan / CSV), identifies everything with open data,
and spits out a static searchable site you host yourself — Netlify, Pages, S3, or just
open the HTML.

- No account, no telemetry; offline unless you opt in with --online
- Open-source (MIT), Python, `pip install mediahound`, or a desktop app
- Movies/music/books/audiobooks/games in one catalog, with watch/listen/find links
- Admin mode to curate; estimates resale value

Live demo (admin pw `changeme`): https://jchirayath.github.io/mediahound/
Code: https://github.com/jchirayath/mediahound
Feedback welcome — especially on metadata accuracy and what media type to add next.
```

### r/DataHoarder  —  lead with "catalog what you already own + export"
**Title:** `Built a free tool to catalog physical media from photos/barcodes → static site + CSV`
**Body:** *(same core, emphasize: CSV import/export, no lock-in, runs locally, batch a whole shelf from one photo, open-data sources so it keeps working.)*

### r/Python  —  lead with the build
**Title:** `MediaHound: turn shelf photos into a searchable media catalog (zero-API-key, open data)`
**Body:** *(emphasize the stack: OCR + MusicBrainz/Wikidata/Open Library SPARQL, offline-first design, static-site output, packaging to PyPI + notarized desktop builds. Link demo + repo, invite contributors — "good first issues" if you have them.)*

### A collector sub (pick by what you own) — r/dvdcollection / r/vinyl / r/bookshelf / r/retrogaming
**Title:** `I made a free app that turns a photo of your shelf into a searchable catalog`
**Body (non-technical!):**
```
Snap a photo of your shelf (or scan a barcode) and it builds a clean website of your
collection with cover art, details, and where to watch/listen — searchable and sortable.
Free, no account, your data stays on your machine. Here's a live sample:
https://jchirayath.github.io/mediahound/
Would love to know what's missing for serious collectors.
```
> Read each sub's self-promo rules first; some require a flair or a "I made this" tag.

Also worth a single post each: **r/opensource**, **r/coolgithubprojects**, **r/macapps** (desktop build).

---

## 3. Product Hunt

**Name:** MediaHound
**Tagline (≤60 chars):** `Turn photos of your shelf into a media catalog you own`
**Topics:** Open Source, Self-Hosted, Productivity, Books, Music
**Gallery:** the demo GIF first (see `demo-gif.md`), then 3–4 screenshots (catalog grid, an item page, the media-type filter, admin mode).
**Description:**
```
MediaHound turns a folder of cover photos — or a barcode scan, or a CSV — into a sleek,
searchable catalog of your movies, music, books, audiobooks, and games.

It identifies each item with open data (MusicBrainz, Wikidata, Open Library; optional
TMDB/OMDb), pulls cover art and details, writes a short blurb, estimates resale value,
and links where to watch/listen/find it. The output is a static website you host
anywhere — no account, no subscription, no API keys required, and it works offline.

Free and open-source (MIT). `pip install mediahound`, or grab the macOS/Windows app.
```
**Maker's first comment:**
```
Hi PH 👋 I built MediaHound because I was tired of buying media I already owned and
didn't want my collection living on someone else's servers. Everything runs locally,
the output is yours, and it's free/OSS. Try the live demo (admin pw `changeme`) and
tell me which medium I should improve next. AMA!
```
**Launch tips:** launch 12:01am PT, line up a few people to try it early, reply to every
comment, and link the GitHub + live demo in the first comment.

---

## 4. Directory listings (long-tail discovery — do these once, benefit for years)

### alternativeto.net  (highest intent — people search "Libib alternative")
List MediaHound as a free/open-source alternative to **Libib**, **CLZ (Collectorz)**, and
**Data Crow**. Suggested blurb:
```
MediaHound is a free, open-source, offline-first cataloger for movies, music, books,
audiobooks, and games. Catalog from shelf photos, barcode/ISBN/UPC scans, or CSV; it
enriches via open data and generates a static website you host yourself — no account.
Platforms: Mac, Windows, Linux, Self-Hosted. License: Open Source (MIT).
```

### awesome-selfhosted  (now via the `awesome-selfhosted-data` repo)
Contributions go to `awesome-selfhosted/awesome-selfhosted-data` as a YAML file in
`software/`, not by editing the README. Draft entry (`software/mediahound.yml`):
```yaml
# title: MediaHound
# website_url: https://github.com/jchirayath/mediahound
# source_code_url: https://github.com/jchirayath/mediahound
# description: Catalog your movies, music, books, audiobooks and games from shelf photos,
#   barcode scans or CSV; enriches via open data and outputs a static, searchable site you host.
# licenses: [MIT]
# platforms: [Python, Docker, deb]
# tags: [Media Streaming - Audio Streaming, Document Management - E-books, Personal Dashboards]
```
⚠️ **Eligibility caveat:** awesome-selfhosted leans toward *network services* you run as a
server. MediaHound is a generator that produces a static site — that's self-hostable, but a
maintainer may consider it out of scope. **Better-fit lists to try first:**
- `awesome-static-website-services` / static-site-generator lists
- `awesome-python` (Utilities)
- niche "awesome" lists for libraries/collections/personal-knowledge
Submit where it clearly fits; don't spam lists where it doesn't (it reads as low-effort).

### Also submit to
LibHunt, OpenAlternative, Toolhunt, and `r/coolgithubprojects`. Add a one-line entry to any
"awesome-cli" or "awesome-cataloging" list you find.

---

## Pre-launch checklist
- [ ] Record the demo GIF (`demo-gif.md`) and put it at the top of the README.
- [ ] Confirm the live demo loads fast and the `changeme` admin password is documented.
- [ ] Tag a clean release so the macOS/Windows download links resolve.
- [ ] Have 2–3 "good first issue" labels for the r/Python + HN dev crowd.
- [ ] Pin a short FAQ in the repo: privacy, which API keys (if any), supported media types.
- [ ] Line up the demo GIF + 3 screenshots for Product Hunt's gallery.
