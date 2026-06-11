# MediaHound brand assets

The mark is a friendly **hound** whose nose is a **play button** — tying "Hound" to "Media."

## Files

| File | Use |
| --- | --- |
| [`mediahound-icon.svg`](mediahound-icon.svg) | The icon mark (app icon, favicon, avatar). Scales to any size. |
| [`mediahound-logo.svg`](mediahound-logo.svg) | Horizontal lockup (icon + wordmark) for **light** backgrounds. |
| [`mediahound-logo-dark.svg`](mediahound-logo-dark.svg) | Horizontal lockup for **dark** backgrounds. |
| [`mediahound-icon.png`](mediahound-icon.png) | 512×512 raster of the icon. |
| `../../mediahound/web/favicon.ico` | Web favicon (16/32/48), shipped in every generated site. |
| `../../packaging/mediahound.icns` · `mediahound.ico` | macOS / Windows desktop-app icons (wired into the PyInstaller build). |

Need other raster sizes? Open `mediahound-icon.svg` in a browser and export, or
`magick mediahound-icon.png -resize 128 out.png` — but **SVG fills/gradients only render
correctly in a real browser** (ImageMagick drops the gradient), so prefer the SVG as the source.

## Palette

| Token | Hex | Where |
| --- | --- | --- |
| Coral | `#FF7A5C` | gradient top |
| Red | `#E11D48` | gradient bottom, nose, "Hound" (light bg) |
| Red (bright) | `#FF6B81` | "Hound" on dark backgrounds |
| Cream | `#F4E4D9` | ears |
| Muzzle | `#F0D5C9` | snout |
| Eye ink | `#3A1020` | eyes |
| Ink | `#1F2430` | "Media" wordmark (light bg) |

## Don'ts

- Don't recolor the gradient or stretch the icon non-uniformly.
- Don't put the dark-background lockup on a light background (and vice-versa) — use the matching file.
- Keep clear space around the lockup equal to the height of the icon's ear.
