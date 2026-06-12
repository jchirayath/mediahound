"""Persistence: the incremental manifest and the generated JSON the website reads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def list_images(input_dir: Path) -> list[Path]:
    if not input_dir.is_dir():
        return []
    return sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")
    )


# Raw-image folder convention: put cover photos under a media-type subfolder. `video` →
# movies (DVD/VHS/Blu-ray/LaserDisc); `audio` → music (CD/vinyl/cassette). `movies`/`music`
# are accepted aliases. Photos left in the input root take the default media type.
MEDIA_FOLDERS = {"video": "movie", "movies": "movie", "movie": "movie",
                 "audio": "music", "music": "music"}


def _images_in(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.name.startswith(".")
    )


def list_media_images(input_dir: Path, default_type: str = "movie") -> list[tuple[Path, str]]:
    """Scan the input dir + its media subfolders → [(path, media_type)].

    Photos in `<input>/video/` are movies, `<input>/audio/` are music; photos directly in
    `<input>/` use `default_type` (back-compat with the old flat layout).
    """
    if not input_dir.is_dir():
        return []
    out: list[tuple[Path, str]] = [(p, default_type) for p in _images_in(input_dir)]
    for sub in sorted(input_dir.iterdir()):
        if sub.is_dir() and not sub.name.startswith("."):
            mt = MEDIA_FOLDERS.get(sub.name.lower())
            if mt:
                out += [(p, mt) for p in _images_in(sub)]
    return out


def _read_json(path: Path, default):
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return default
    return default


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


class Store:
    """Owns all the JSON files under <output>/data/."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.manifest_path = data_dir / "manifest.json"
        self.collection_path = data_dir / "collection.json"
        self.unidentified_path = data_dir / "unidentified.json"
        self.seen_overrides_path = data_dir / "seen-overrides.json"
        self.identify_queue_path = data_dir / "identify-queue.json"
        self.corrections_path = data_dir / "corrections.json"
        self.loans_path = data_dir / "loans.json"

        self.manifest: dict = _read_json(self.manifest_path, {})
        self.collection: list = _read_json(self.collection_path, [])
        self.unidentified: list = _read_json(self.unidentified_path, [])
        self.seen_overrides: dict = _read_json(self.seen_overrides_path, {})
        self.identify_queue: dict = _read_json(self.identify_queue_path, {})
        self.corrections: dict = _read_json(self.corrections_path, {})
        # Personal lending tracker (id → {to, since, returned}) — admin-only, never published.
        self.loans: dict = _read_json(self.loans_path, {})

        self._collection_by_id = {m["id"]: m for m in self.collection}

    # -- queries -----------------------------------------------------------
    def is_processed(self, file_hash: str) -> bool:
        return file_hash in self.manifest

    def queued_identity(self, file_hash: str) -> dict | None:
        """Manual identification supplied via identify.html → identify-queue.json."""
        return self.identify_queue.get(file_hash)

    # -- mutations ---------------------------------------------------------
    def record(self, file_hash: str, filename: str, status: str, movie_id: str | None, when: str):
        self.manifest[file_hash] = {
            "file": filename,
            "hash": file_hash,
            "status": status,
            "movie_id": movie_id,
            "processed_at": when,
        }

    def upsert_movie(self, movie: dict):
        mid = movie["id"]
        # preserve seen-state from a committed override file
        ov = self.seen_overrides.get(mid)
        if ov:
            movie["seen"] = ov.get("seen", movie.get("seen", False))
            movie["date_seen"] = ov.get("date_seen", movie.get("date_seen"))
        if mid in self._collection_by_id:
            old = self._collection_by_id[mid]
            # accumulate cover photos from every duplicate copy into one gallery
            merged = list(old.get("images", []))
            for im in movie.get("images", []):
                if im and im not in merged:
                    merged.append(im)
            old.update(movie)
            old["images"] = merged
        else:
            self._collection_by_id[mid] = movie
            self.collection.append(movie)
        # if this title was previously unidentified, drop it from that list
        self.unidentified = [u for u in self.unidentified if u.get("id") != mid]

    def find_movie(self, mid: str) -> dict | None:
        return self._collection_by_id.get(mid)

    def delete_movie(self, mid: str) -> bool:
        m = self._collection_by_id.pop(mid, None)
        if m is None:
            return False
        self.collection = [x for x in self.collection if x.get("id") != mid]
        # mark the source image(s) as deleted so they are NOT re-added on the next build
        for rec in self.manifest.values():
            if rec.get("movie_id") == mid:
                rec["status"] = "deleted"
                rec["movie_id"] = None
        return True

    def add_unidentified(self, item: dict):
        if not any(u.get("hash") == item.get("hash") for u in self.unidentified):
            self.unidentified.append(item)

    def remove_unidentified_by_hash(self, file_hash: str):
        self.unidentified = [u for u in self.unidentified if u.get("hash") != file_hash]

    def apply_seen_overrides(self):
        for m in self.collection:
            ov = self.seen_overrides.get(m["id"])
            if ov:
                m["seen"] = ov.get("seen", m.get("seen", False))
                m["date_seen"] = ov.get("date_seen", m.get("date_seen"))

    # -- flush -------------------------------------------------------------
    def save(self):
        self.apply_seen_overrides()
        self.collection.sort(key=lambda m: (m.get("title") or "").lower())
        _write_json(self.manifest_path, self.manifest)
        _write_json(self.collection_path, self.collection)
        _write_json(self.unidentified_path, self.unidentified)
        # create empty round-trip files on first run so the site can fetch them (these are
        # admin-only and excluded from publish, so an empty local copy leaks nothing)
        for p in (self.seen_overrides_path, self.identify_queue_path,
                  self.corrections_path, self.loans_path):
            if not p.is_file():
                _write_json(p, {})
