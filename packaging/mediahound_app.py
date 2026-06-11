"""PyInstaller entry point.

The desktop module uses package-relative imports (`from .config import …`), which only
resolve when it's imported as part of the `mediahound` package — not when PyInstaller runs
`desktop.py` directly as `__main__`. This launcher imports it the right way.
"""
from mediahound.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
