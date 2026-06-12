"""Desktop app — open the MediaHound editor in a native window.

`mediahound gui` (or the bundled double-click app) sets up a library, starts the local
admin server in the background, and opens it in a native webview window. If a native
webview isn't available (e.g. headless, or `pywebview` not installed), it falls back to
opening the system browser — so the same entry point works everywhere.

Packaging note: this module is the PyInstaller entry point (`mediahound-gui`), bundled
into a .app / .exe so non-technical users never touch Python or a terminal.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from .config import load_config

APP_NAME = "MediaHound"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def default_library() -> Path:
    """Where a double-clicked app keeps its library by default."""
    return Path.home() / "MediaHound Library"


def prepare(directory: str | None = None, log=print):
    """Ensure a library exists (scaffold + an initial empty build) and return its Config.

    With no directory, reopen the most-recently-used library (so switching libraries in the app
    sets the default for next launch), falling back to ~/MediaHound Library on a first run."""
    import argparse

    from . import libraries, pipeline
    from .cli import cmd_init
    if directory:
        site = Path(directory).resolve()
    else:
        recent = libraries.list_recent()
        site = Path(recent[0]["path"]) if recent else default_library()
    config_path = site / "config.toml"
    if not config_path.is_file():
        log(f"Setting up your library at {site} …")
        cmd_init(argparse.Namespace(directory=str(site), force=False))
    cfg = load_config(config_path)
    # Offline rebuild on every open → refreshes the app UI to this version (sync_web_assets) and
    # regenerates the site from existing data. Fast (no online lookups); an empty catalog is fine.
    pipeline.build(cfg, online=False, log=log)
    return cfg


def _wait_ready(port: int, tries: int = 100) -> None:
    for _ in range(tries):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1).read()
            return
        except OSError:
            time.sleep(0.05)


def _start_server(cfg, port: int, log=print) -> None:
    from . import serve as serve_mod
    threading.Thread(
        target=serve_mod.serve,
        kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=True, open_browser=False, log=log),
        daemon=True,
    ).start()
    _wait_ready(port)


def run(directory: str | None = None, log=print) -> int:
    cfg = prepare(directory, log=log)
    port = _free_port()
    url = f"http://127.0.0.1:{port}/"
    _start_server(cfg, port, log=log)

    try:
        import webview  # native window (optional dependency)
    except Exception:                                    # noqa: BLE001 - fall back to the browser
        log(f"Opening {APP_NAME} in your browser → {url}")
        log("(For a native window, install with:  pip install \"mediahound[desktop]\")")
        webbrowser.open(url)
        try:
            threading.Event().wait()                     # keep the background server alive
        except KeyboardInterrupt:
            pass
        return 0

    webview.create_window(APP_NAME, url, width=1200, height=820, min_size=(820, 600))
    # Use the OS-native backend (macOS Cocoa/WebKit) — no Qt. Keeps the app small and uses
    # only built-in system frameworks. autodetect elsewhere (Windows → EdgeChromium).
    gui = "cocoa" if sys.platform == "darwin" else None
    webview.start(gui=gui)                               # blocks until the window is closed
    return 0


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="mediahound-gui", description=f"{APP_NAME} desktop app")
    p.add_argument("directory", nargs="?",
                   help="library folder (default: ~/MediaHound Library)")
    args = p.parse_args(argv)
    return run(args.directory)


if __name__ == "__main__":
    raise SystemExit(main())
