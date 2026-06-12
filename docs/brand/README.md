# MediaHound brand assets

The mark is a friendly **beagle wearing headphones**, framed by a **retro TV** (with antennas) over
an **open book** — movies + music + the catalog, in one image. The wordmark sets **media** in brand
orange and **hound** in brand ink.

![MediaHound logo](mediahound-logo.png)

## Files

| File | Use |
| --- | --- |
| [`mediahound-icon.png`](mediahound-icon.png) | The icon mark — TV + hound, no wordmark (app icon, favicon, avatar). 512×512, transparent. |
| [`mediahound-logo.png`](mediahound-logo.png) | Full horizontal lockup (icon + wordmark) for **light** backgrounds (README, wiki, docs). |
| `../../mediahound/web/favicon.ico` | Web favicon (16/32/48/64), shipped in every generated site. |
| `../../mediahound/web/assets/img/apple-touch-icon.png` | iOS home-screen icon (180×180, opaque). |
| `../../packaging/mediahound.icns` · `mediahound.ico` | macOS / Windows desktop-app icons (wired into the PyInstaller build). |

All raster assets derive from the master artwork. To regenerate other sizes:
`magick mediahound-icon.png -resize 128 out.png`.

## Palette

| Token | Hex | Where |
| --- | --- | --- |
| Brand orange | `#E97B0C` | TV frame, "media" wordmark, UI accent |
| Brand ink | `#16232A` | "hound" wordmark, headphones, antennas, outlines |
| Hound tan | `#D7822F` | the beagle's coat |
| Muzzle | `#FFFFFF` | snout / face highlights |
| Tongue | `#F2654E` | the dog's tongue |
| Book / page edge | `#2C8C9C` | the open book under the TV |

## Typography

- **Wordmark / brand font:** **[Fredoka](https://fonts.google.com/specimen/Fredoka)** (Google Fonts,
  weights 400–700) — a rounded geometric sans that matches the logo's friendly lettering. Used for the
  site title, headings, and the brand mark in the web app.
- **Body / UI text:** **Inter** (kept for dense catalog metadata where legibility matters most).

## Don'ts

- Don't recolor the orange or the ink, or stretch the icon non-uniformly.
- Don't put the wordmark lockup on a dark background — the ink "hound" disappears; use the **icon**
  (transparent) on dark surfaces instead.
- Keep clear space around the lockup equal to the height of the TV's antenna knob.
