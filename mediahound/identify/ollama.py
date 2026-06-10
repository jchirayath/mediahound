"""Optional local identifier: an open vision model served by Ollama (no cloud, no key).

Enabled via config (`[identify] provider = "ollama"`). Requires a running Ollama with a
vision model pulled, e.g. `ollama pull llava`.
"""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from .base import Identification, Identifier
from .cloud import _PROMPT, _extract_json


class OllamaIdentifier(Identifier):
    name = "ollama"

    def __init__(self, cfg: dict):
        self.model = cfg.get("model", "llava")
        self.host = cfg.get("host", "http://localhost:11434").rstrip("/")

    def identify(self, image_path: Path, jpeg_bytes: bytes) -> Identification:
        b64 = base64.standard_b64encode(jpeg_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "prompt": _PROMPT,
            "images": [b64],
            "stream": False,
            "format": "json",
        }
        resp = requests.post(f"{self.host}/api/generate", json=payload, timeout=180)
        resp.raise_for_status()
        text = resp.json().get("response", "")
        obj = _extract_json(text) or {}
        fmt = (obj.get("format") or "Unknown").title().replace("Dvd", "DVD").replace("Vhs", "VHS")
        if fmt not in ("DVD", "VHS", "Blu-ray", "Unknown"):
            fmt = "Unknown"
        year = obj.get("year")
        try:
            year = int(year) if year else None
        except (TypeError, ValueError):
            year = None
        return Identification(
            identified=bool(obj.get("identified") and obj.get("title")),
            title=obj.get("title") or None,
            year=year,
            format=fmt,
            language=obj.get("language") or None,
            confidence=float(obj.get("confidence") or 0.0),
            intro=obj.get("intro") or None,
            raw=obj,
        )
