"""Recent-libraries list — power the UI library switcher.

A MediaHound library is just a directory with a `config.toml`. This module keeps a small
recents file (`$XDG_CONFIG_HOME/mediahound/recent.json`, default `~/.config/mediahound/`) so the
desktop app / admin UI can offer "open / switch library" without the user retyping paths. It only
stores directory paths + titles — never any catalog data — and self-heals (entries whose
`config.toml` has vanished are dropped on read).
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

_MAX = 12


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "mediahound"


def recent_path() -> Path:
    return _config_dir() / "recent.json"


def _read() -> list[dict]:
    p = recent_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (ValueError, OSError):
        return []


def _write(items: list[dict]) -> None:
    p = recent_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def is_library(path: str | Path) -> bool:
    """True if `path` is a directory containing a config.toml (a MediaHound library)."""
    return (Path(path).expanduser() / "config.toml").is_file()


def list_recent() -> list[dict]:
    """Recent libraries, newest first, pruned to those that still exist on disk."""
    out, seen = [], set()
    for it in _read():
        path = str(it.get("path") or "")
        if not path or path in seen or not is_library(path):
            continue
        seen.add(path)
        out.append({"path": path, "title": it.get("title") or Path(path).name,
                    "last_opened": it.get("last_opened")})
    return out


def add_recent(path: str | Path, title: str | None = None) -> list[dict]:
    """Record a library as most-recently-opened (upsert by directory). Returns the new list."""
    path = str(Path(path).expanduser().resolve())
    if not is_library(path):
        return list_recent()
    items = [it for it in _read() if str(it.get("path") or "") != path]
    items.insert(0, {"path": path, "title": title or Path(path).name,
                     "last_opened": datetime.now(UTC).isoformat(timespec="seconds")})
    items = items[:_MAX]
    _write(items)
    return list_recent()


def remove_recent(path: str | Path) -> list[dict]:
    path = str(Path(path).expanduser().resolve())
    _write([it for it in _read() if str(it.get("path") or "") != path])
    return list_recent()
