"""Default, zero-key identifier: Tesseract OCR reads the cover text.

Heuristic: the title is usually the largest, most-confident block of text on the
cover, so we score each OCR line by (font height x confidence) and pick the best.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..imaging import ocr_image
from .base import Identification, Identifier

_FORMAT_PATTERNS = [
    ("Blu-ray", re.compile(r"blu[\s\-]?ray", re.I)),
    ("DVD", re.compile(r"\bdvd\b", re.I)),
    ("VHS", re.compile(r"\bvhs\b|\bvideo\s*cassette\b", re.I)),
]
_YEAR_RE = re.compile(r"\b(19[3-9]\d|20[0-4]\d)\b")
# Lines that are obviously not a title.
_NOISE_RE = re.compile(
    r"widescreen|full screen|fullscreen|color|colour|minutes|rated|warner|paramount|"
    r"universal|sony|columbia|disney|pictures|entertainment|home video|all rights|"
    r"dolby|digital|surround|region|www\.|http|closed caption|bonus|special|edition",
    re.I,
)


class TesseractIdentifier(Identifier):
    name = "tesseract"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def identify(self, image_path: Path, jpeg_bytes: bytes) -> Identification:
        try:
            import pytesseract
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pytesseract is required for the 'tesseract' identifier. "
                "Install it (`pip install pytesseract`) and the Tesseract engine "
                "(`brew install tesseract` / `apt install tesseract-ocr`)."
            ) from exc

        img = ocr_image(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        full_text = pytesseract.image_to_string(img)

        # Group words into lines, tracking confidence + glyph height.
        lines: dict[tuple, dict] = {}
        n = len(data["text"])
        for i in range(n):
            word = (data["text"][i] or "").strip()
            conf = float(data["conf"][i]) if data["conf"][i] not in ("-1", -1) else -1.0
            if not word or conf < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            ln = lines.setdefault(key, {"words": [], "confs": [], "h": 0})
            ln["words"].append(word)
            ln["confs"].append(conf)
            ln["h"] = max(ln["h"], int(data["height"][i]))

        best = None
        best_score = 0.0
        for ln in lines.values():
            text = " ".join(ln["words"]).strip()
            letters = re.sub(r"[^A-Za-z]", "", text)
            if len(letters) < 3 or _NOISE_RE.search(text):
                continue
            avg_conf = sum(ln["confs"]) / len(ln["confs"]) / 100.0
            score = ln["h"] * avg_conf * min(len(letters), 24)
            if score > best_score:
                best_score, best = score, {"text": text, "conf": avg_conf}

        fmt = "Unknown"
        for label, pat in _FORMAT_PATTERNS:
            if pat.search(full_text):
                fmt = label
                break
        year = None
        ym = _YEAR_RE.search(full_text)
        if ym:
            year = int(ym.group(1))

        if not best:
            return Identification(False, format=fmt, confidence=0.0,
                                  raw={"ocr_text": full_text})

        title = _clean_title(best["text"])
        # Confidence blends OCR confidence with how "title-like" the pick was.
        confidence = round(min(0.95, 0.35 + best["conf"] * 0.6), 3)
        return Identification(
            identified=bool(title),
            title=title,
            year=year,
            format=fmt,
            confidence=confidence,
            raw={"ocr_text": full_text, "picked": best["text"]},
        )


def _clean_title(text: str) -> str:
    text = re.sub(r"[^\w\s:&'!.\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -:.")
    if text.isupper():
        text = text.title()
    return text
