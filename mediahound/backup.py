"""Back up / restore a MediaHound library — protect the curation work.

A library's irreplaceable value is its **source of truth**: the cover photos in `RawImages/`,
the generated `data/` (catalog + all your manual fixes, ratings, notes, tags, loans), and
`config.toml`. `make_backup()` bundles exactly those into a single zip; `restore_backup()`
re-creates a library from one.

Secrets are never backed up: `.env` lives next to `config.toml` but is excluded, and provider
keys live in the OS keychain (not in any file), so they can't end up in a backup either.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from .config import Config

_EXCLUDE_NAMES = {".env"}                         # secrets — never in a backup
_EXCLUDE_DATA = {".metadata-cache.json"}          # regenerable cache; skip to keep backups small


def _add_tree(zf: zipfile.ZipFile, root: Path, arc_prefix: str, skip: set[str] | None = None) -> int:
    if not root.is_dir():
        return 0
    n = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name in _EXCLUDE_NAMES or (skip and p.name in skip):
            continue
        rel = p.relative_to(root)
        zf.write(p, f"{arc_prefix}/{'/'.join(rel.parts)}")
        n += 1
    return n


def make_backup(cfg: Config, out_path: Path, no_photos: bool = False) -> int:
    """Write a backup zip of config.toml + data/ (+ RawImages/ unless no_photos). Returns
    the number of files archived. `no_photos` makes a small, quick, curation-only backup."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    config_file = cfg.base_dir / "config.toml"
    input_dir = cfg.input_dir
    data_dir = cfg.data_dir
    files = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if config_file.is_file():
            zf.write(config_file, "config.toml")
            files += 1
        files += _add_tree(zf, data_dir, "data", skip=_EXCLUDE_DATA)
        if not no_photos:
            files += _add_tree(zf, input_dir, input_dir.name)
    return files


def restore_backup(zip_path: Path, dest: Path) -> int:
    """Extract a backup zip into `dest`, re-creating the library. Returns the file count.
    Refuses entries with absolute paths or `..` traversal (zip-slip protection)."""
    zip_path, dest = Path(zip_path), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    dest_res = dest.resolve()
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            target = (dest / name).resolve()
            if Path(name).is_absolute() or dest_res not in target.parents and target != dest_res:
                raise ValueError(f"unsafe path in backup: {name!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                out.write(src.read())
            n += 1
    return n
