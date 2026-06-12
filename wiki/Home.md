<p align="center">
  <img src="https://raw.githubusercontent.com/jchirayath/mediahound/main/docs/brand/mediahound-logo.png" width="340" alt="MediaHound">
</p>

# MediaHound Wiki

**MediaHound** turns photos of your DVD / VHS / Blu-ray and **CD / vinyl / cassette** covers — or a
CSV — into a sleek, searchable, self-hosted catalog of your **movies *and* music**. Offline-first,
zero-key by default, open-source (MIT). Everything stays on your computer.

**▶ [Live demo](https://jchirayath.github.io/mediahound/)** · 📦 [PyPI](https://pypi.org/project/mediahound/) · 💻 [Source](https://github.com/jchirayath/mediahound)

## Three ways to use it

| | For whom | How |
| --- | --- | --- |
| 🖥️ **Desktop app** | Non-technical | Download the [macOS](https://github.com/jchirayath/mediahound/releases/latest/download/MediaHound-macOS.zip) / [Windows](https://github.com/jchirayath/mediahound/releases/latest/download/MediaHound-Windows.zip) app, unzip, open. See **[[Desktop App]]**. |
| 🐍 **pip** | Have Python | `pip install mediahound` then `mediahound app`. |
| 🛠️ **From source** | Hacking on it | `git clone … && pip install -e .` |

## Quick start (CLI)

```bash
pip install mediahound
mediahound app          # sets up a library and opens the editor in your browser
```

…then click **➕ Add photos** to drag in your cover pics. No config files, no separate commands.

## Guides

- **[[Desktop App]]** — download / `mediahound gui` / building / code-signing.
- **[[Adding Media]]** — drag-and-drop, 📱 phone upload (QR), and CSV import.
- **[[Editing and Persisting Changes]]** — fix titles & make them stick; why edits "revert" and how to prevent it.
- **[[Publishing Your Catalog]]** — one-click 🌐 Publish to the web, or static hosting.
- **[[Configuration and API Keys]]** — `config.toml`, providers, and setting keys in the OS keychain.
- **[[Command Reference]]** — every CLI command and flag.
- **[[Privacy]]** — what stays local, and the only times data leaves your computer.

## How it works

A **Python CLI** reads cover photos → identifies each item → enriches it (cover art, cast/artist,
genres, runtime/tracklist, where to watch/listen, resale value) → writes a **static web app** you can
search and curate. The two halves meet at a folder of JSON files. Full design:
[ARCHITECTURE.md](https://github.com/jchirayath/mediahound/blob/main/ARCHITECTURE.md).
