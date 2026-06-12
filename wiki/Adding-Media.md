# Adding media

Several ways to get titles into your catalog. All of them work in the admin console under
`mediahound app` / `serve --admin` / the desktop app (the photo / scan / CSV options live under the
**➕ Add** menu; Discogs is under **🔗 Connect**).

## ➕ Drag-and-drop photos (easiest)

Click **➕ Add photos**, choose 🎬 Movies or 🎵 Music, and drag your cover pics in (or pick files).
Each photo is validated, saved into the right folder, and catalogued automatically. No file copying.

## 📱 From your phone (QR)

```bash
mediahound app --phone
```

A **QR code** prints in the terminal. Scan it with your phone on the **same Wi-Fi**, tap
**➕ Add photos → Take Photo**, and the covers upload straight into your catalog.

- Uploads are **token-protected** — only the phone that scanned the code can add photos.
- Nothing leaves your network. Use it on a trusted Wi-Fi only.
- API-key and Publish actions stay disabled in phone mode (localhost-only).

## 📷 Scan a barcode (exact, not fuzzy)

Click **➕ Add → 📷 Scan barcode**. Point your phone/laptop camera at the UPC/EAN on the back of a
case (or type the digits) and the **exact release** is identified — no cover photo, no OCR guesswork.
Music resolves via MusicBrainz/Discogs; **books** by **ISBN** (a 978/979 barcode) via **Open Library**
(auto-detected — no need to pick the type); movies via a product-name lookup, then the normal title path.
Local decoding in a build needs the optional extra: `pip install "mediahound[barcode]"`.

## 💿 Import a Discogs collection

Already keep your records/CDs on **Discogs**? Click **🔗 Connect → Import from Discogs** (or
`mediahound import-discogs <username>`) to pull the whole collection in with art and metadata. Add a
Discogs token in **Settings → API keys** to raise the rate limit.

## ⬆ Import a CSV (no photos needed)

Click **⬆ Import list** (or `mediahound import yourlist.csv`). Only a `title` column is required;
extra columns (year, artist, format, …) fill in what they can, and `--online` enriches each row.
See [`examples/sample-import.csv`](https://github.com/jchirayath/mediahound/blob/main/examples/sample-import.csv).

## 📁 The RawImages folders (CLI)

When you scaffold with `mediahound init`, photos go here and are routed by media type:

```
RawImages/
  video/   → movies (DVD, VHS, Blu-ray, LaserDisc)
  audio/   → music  (CD, vinyl, cassette)
```

Photos left directly in `RawImages/` are treated as movies. Then run `mediahound build`
(add `--online` to fetch cover art & metadata). Builds are **incremental** — only new photos
(tracked by sha256) are processed.

## What happens to an added photo

It's identified (OCR / vision), enriched (movies: TMDB / OMDb / Wikidata + JustWatch; music:
MusicBrainz + Cover Art Archive), and added to the catalog. Couldn't identify it? It lands in the
**Unidentified** queue where you can name it by hand. See **[[Editing and Persisting Changes]]**.
