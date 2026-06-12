# Desktop app

A double-clickable MediaHound app — no Python, no terminal. It opens the editor in a native window
and keeps your library in **`~/MediaHound Library`**. Works fully offline.

## Download

- **macOS:** [MediaHound-macOS.zip](https://github.com/jchirayath/mediahound/releases/latest/download/MediaHound-macOS.zip)
- **Windows:** [MediaHound-Windows.zip](https://github.com/jchirayath/mediahound/releases/latest/download/MediaHound-Windows.zip)

Unzip and open. The macOS build is **signed & notarized** by Apple, so it opens cleanly. The Windows
build may show a one-time SmartScreen prompt (**More info → Run anyway**) until code-signing is live.

## If you have Python

```bash
pip install "mediahound[desktop]"   # adds pywebview for the native window
mediahound gui                      # opens the editor in a window (browser fallback without [desktop])
```

`mediahound gui` sets up the library if needed, starts the local admin server, and opens it in a
window. It's the same engine the bundled app runs.

## Build it yourself

PyInstaller can't cross-compile — build on the OS you want:

```bash
bash packaging/build-desktop.sh     # → dist/MediaHound.app (macOS) or dist/MediaHound/ (Windows)
```

CI builds both automatically — see [`.github/workflows/desktop.yml`](https://github.com/jchirayath/mediahound/blob/main/.github/workflows/desktop.yml).

## Code-signing

- **macOS** — signed with a **Developer ID** certificate and **notarized** via Fastlane
  ([`fastlane/Fastfile`](https://github.com/jchirayath/mediahound/blob/main/fastlane/Fastfile)).
- **Windows** — free signing for this open-source project via **SignPath Foundation**, or your own
  cert / Azure Trusted Signing.

Full setup (secrets, identities, the SignPath application): see
[SIGNING.md](https://github.com/jchirayath/mediahound/blob/main/SIGNING.md).

## Troubleshooting

- **macOS "unidentified developer"** — only happens on unsigned builds; right-click → **Open** once.
- **Nothing happens / window doesn't appear** — make sure you opened the unzipped app (not from inside
  the zip). The app needs to write to `~/MediaHound Library`.
