"""Identifier interface shared by every identification backend."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Identification:
    identified: bool
    title: str | None = None
    year: int | None = None
    format: str = "Unknown"          # DVD | VHS | Blu-ray | Unknown
    language: str | None = None
    confidence: float = 0.0          # 0..1
    intro: str | None = None         # some identifiers (e.g. Claude) also write the hook
    artist: str | None = None        # music: the performing artist (sharpens the lookup query)
    raw: dict = field(default_factory=dict)


class Identifier:
    """Subclasses implement identify(); name is used in logs/manifest."""

    name = "base"

    def identify(self, image_path: Path, jpeg_bytes: bytes) -> Identification:
        raise NotImplementedError
