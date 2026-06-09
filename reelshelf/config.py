"""Configuration loading: parse config.toml, resolve paths, load .env secrets."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path


DEFAULTS = {
    "site": {"title": "My Movie Collection", "subtitle": ""},
    "paths": {"input": "RawImages", "output": "."},
    "identify": {"provider": "tesseract", "confidence_threshold": 0.55},
    "metadata": {"provider": "wikidata"},
    "resale": {"ebay_tld": "com"},
    "streaming": {"enabled": True, "country": "US"},
    "admin": {"password": "changeme"},
    "view": {"columns": 5},
}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE per line). Does not overwrite existing env."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


class Config:
    def __init__(self, data: dict, base_dir: Path):
        self.data = data
        self.base_dir = base_dir

    # -- section accessors -------------------------------------------------
    @property
    def site(self) -> dict:
        return self.data["site"]

    @property
    def identify(self) -> dict:
        return self.data["identify"]

    @property
    def metadata(self) -> dict:
        return self.data["metadata"]

    @property
    def resale(self) -> dict:
        return self.data["resale"]

    @property
    def streaming(self) -> dict:
        return self.data.get("streaming", {"enabled": True, "country": "US"})

    @property
    def admin(self) -> dict:
        return self.data.get("admin", {"password": "changeme"})

    @property
    def view(self) -> dict:
        return self.data.get("view", {"columns": 4})

    # -- resolved paths ----------------------------------------------------
    def _resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (self.base_dir / path).resolve()

    @property
    def input_dir(self) -> Path:
        return self._resolve(self.data["paths"]["input"])

    @property
    def output_dir(self) -> Path:
        return self._resolve(self.data["paths"]["output"])

    @property
    def data_dir(self) -> Path:
        return self.output_dir / "data"

    @property
    def posters_dir(self) -> Path:
        return self.output_dir / "posters"


def load_config(config_path: str | os.PathLike) -> Config:
    config_path = Path(config_path).resolve()
    base_dir = config_path.parent
    load_dotenv(base_dir / ".env")
    with open(config_path, "rb") as fh:
        user = tomllib.load(fh)
    merged = _deep_merge(DEFAULTS, user)
    return Config(merged, base_dir)
