"""Identifier providers: read title/year/format from a cover photo."""
from __future__ import annotations

from .base import Identification, Identifier


def get_identifier(cfg) -> Identifier:
    name = cfg.identify.get("provider", "tesseract").lower()
    if name == "tesseract":
        from .tesseract import TesseractIdentifier
        return TesseractIdentifier(cfg.identify)
    if name == "claude":
        from .cloud import ClaudeIdentifier
        return ClaudeIdentifier(cfg.identify.get("claude", {}))
    if name == "ollama":
        from .ollama import OllamaIdentifier
        return OllamaIdentifier(cfg.identify.get("ollama", {}))
    raise ValueError(f"Unknown identify provider: {name!r}")


__all__ = ["Identification", "Identifier", "get_identifier"]
