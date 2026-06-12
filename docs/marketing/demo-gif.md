# Demo GIF / video — the highest-impact asset

A 15–20s loop of **shelf photo → polished catalog** will out-convert any paragraph.
Put it at the very top of the README and reuse it on HN, Product Hunt, Reddit, and X.

## Storyboard (keep it ≤20s, no narration needed)

| t (s) | Shot | On screen |
|------|------|-----------|
| 0–3 | A folder/grid of cover **photos** (DVDs/CDs/books) | "Your shelf, photographed" |
| 3–7 | Terminal: `mediahound build …` running, rows resolving | covers + titles filling in |
| 7–11 | Browser opens the generated catalog grid | posters/album art in a clean grid |
| 11–15 | Click the **🎬/🎵/📚/🎧/🎮 filter**, type in search | instant filter + search |
| 15–18 | Open one item page | blurb, metadata, watch/listen links, resale value |
| 18–20 | Cut back to the full grid (loop point) | logo + `pip install mediahound` |

Two output formats:
- **GIF** for the GitHub README (autoplays inline). Keep it **< 5 MB** (≤ 1280px wide, ~12–15 fps).
- **MP4/WebM** for Product Hunt, X, LinkedIn (smaller, crisper). Keep an `.mp4` copy too.

---

## Option A — pure CLI GIF with `vhs` (easiest, fully scripted, reproducible)

[`vhs`](https://github.com/charmbracelet/vhs) records a terminal from a script — no manual capture.

```bash
brew install vhs            # or: go install github.com/charmbracelet/vhs@latest
vhs docs/marketing/mediahound.tape
```

Create `docs/marketing/mediahound.tape`:
```tape
Output docs/brand/demo-cli.gif
Set FontSize 20
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 24

Type "pip install mediahound"      Enter   Sleep 1s
Type "mediahound init demo"        Enter   Sleep 1s
Type "mediahound build --config demo/config.toml --mock"   Enter   Sleep 3s
Type "cd demo && python3 -m http.server 8000"   Enter   Sleep 1s
# now screen-record the browser separately (Option B) for the catalog half
```
This nails the "30 seconds, no keys" half. Pair it with a short browser clip for the catalog.

---

## Option B — browser/app screen capture → optimized GIF (the money shot)

The catalog UI is what sells it. Record the browser, then compress.

**1. Record** (macOS): `Cmd+Shift+5` → record a tight window region of the demo site
(https://jchirayath.github.io/mediahound/), or run a local build and record that. ~20s:
grid → filter chips → search → one item page → back to grid. Save as `raw.mov`.

**2. Trim** to the best ~18s:
```bash
ffmpeg -ss 00:00:02 -to 00:00:20 -i raw.mov -an -c copy trimmed.mov
```

**3a. High-quality GIF with `gifski`** (best quality/size):
```bash
brew install gifski
ffmpeg -i trimmed.mov -vf "scale=1200:-1:flags=lanczos,fps=15" frames/%04d.png
gifski -o docs/brand/demo.gif --fps 15 --quality 80 frames/*.png
```

**3b. …or pure ffmpeg (palette method)** if you skip gifski:
```bash
ffmpeg -i trimmed.mov -vf "fps=15,scale=1200:-1:flags=lanczos,palettegen" palette.png
ffmpeg -i trimmed.mov -i palette.png -lavfi "fps=15,scale=1200:-1:flags=lanczos[x];[x][1:v]paletteuse" docs/brand/demo.gif
```

**4. Also export an MP4** (for PH/X — much smaller than the GIF):
```bash
ffmpeg -i trimmed.mov -vf "scale=1280:-2:flags=lanczos" -c:v libx264 -pix_fmt yuv420p -movflags +faststart -an docs/brand/demo.mp4
```

**5. Check size** (`ls -lh docs/brand/demo.gif`). If > 5 MB: drop to `scale=1000`, `fps=12`,
or shorten to 15s. Loop should be seamless (start and end on the full grid).

---

## Slot it into the README hero

Replace the static screenshot near the top of `README.md`:
```markdown
<p align="center">
  <a href="https://jchirayath.github.io/mediahound/">
    <img alt="MediaHound demo — shelf photos to a searchable catalog" src="docs/brand/demo.gif" width="800">
  </a>
</p>
```
Keep the existing `docs/screenshot.jpg` as a fallback below it.
