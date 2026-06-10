"""Optional cloud identifier: Anthropic Claude vision (best accuracy; also writes the intro).

Enabled via config (`[identify] provider = "claude"`). Needs ANTHROPIC_API_KEY in the
environment or the instance's .env. No key is ever read from or written to the repo.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

import requests

from .base import Identification, Identifier

_API_URL = "https://api.anthropic.com/v1/messages"

_PROMPT = (
    "You are cataloguing a physical home-video product from a photo of its case/cover.\n"
    "Identify the movie or TV title as precisely as you can. Then respond with ONLY a JSON "
    "object (no prose) with these fields:\n"
    '  "identified": boolean,\n'
    '  "title": the canonical title (string) or null,\n'
    '  "year": release year (integer) or null,\n'
    '  "format": one of "DVD", "VHS", "Blu-ray", "Unknown" (judge from the physical case),\n'
    '  "language": primary spoken language (string) or null,\n'
    '  "confidence": 0..1 how sure you are of the title,\n'
    '  "intro": a vivid 1-2 sentence HOOK that makes someone want to watch it — '
    "NOT a plot summary, no spoilers, no \"this film is about\". Make it enticing.\n"
    "If you cannot read a title, set identified=false and confidence low."
)


class ClaudeIdentifier(Identifier):
    name = "claude"

    def __init__(self, cfg: dict):
        self.model = cfg.get("model", "claude-haiku-4-5")
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to the instance's .env "
                "(gitignored) or your environment to use the 'claude' identifier."
            )

    def identify(self, image_path: Path, jpeg_bytes: bytes) -> Identification:
        b64 = base64.standard_b64encode(jpeg_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "max_tokens": 500,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": _PROMPT},
                ],
            }],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        resp = requests.post(_API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        text = "".join(
            block.get("text", "") for block in body.get("content", [])
            if block.get("type") == "text"
        )
        obj = _extract_json(text)
        if not obj:
            return Identification(False, confidence=0.0, raw={"response": text})

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
            title=(obj.get("title") or None),
            year=year,
            format=fmt,
            language=obj.get("language") or None,
            confidence=float(obj.get("confidence") or 0.0),
            intro=(obj.get("intro") or None),
            raw=obj,
        )


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
    return None
