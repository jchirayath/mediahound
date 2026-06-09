"""Image helpers: prepare a compact JPEG for vision/OCR and save thumbnails."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def _load(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # honor phone orientation
    return img.convert("RGB")


def prepared_jpeg(path: Path, max_edge: int = 1024, quality: int = 85) -> bytes:
    """Downscaled JPEG bytes — small payload for a vision API or OCR."""
    img = _load(path)
    img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def ocr_image(path: Path, max_edge: int = 1600) -> Image.Image:
    """Higher-res, contrast-normalized grayscale image that OCR reads better."""
    img = _load(path)
    img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    gray = ImageOps.grayscale(img)
    return ImageOps.autocontrast(gray)


def save_thumbnail(path: Path, dest: Path, max_edge: int = 360, portrait: bool = False) -> None:
    img = _load(path)
    if portrait and img.width > img.height:
        img = img.rotate(90, expand=True)  # landscape cover photo → upright portrait
    img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="JPEG", quality=82)


def rotate_file(path: Path, degrees: int) -> bool:
    """Rotate an image file clockwise by degrees (90/180/270) in place."""
    degrees = degrees % 360
    if degrees == 0 or not path.is_file():
        return False
    img = Image.open(path).convert("RGB")
    img = img.rotate(-degrees, expand=True)  # PIL rotates counter-clockwise
    img.save(path, format="JPEG", quality=85)
    return True


def make_placeholder_poster(text: str, dest: Path, color=(40, 44, 64)) -> None:
    """A simple title-card poster used by --mock so the demo has real images."""
    w, h = 500, 750
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    for i in range(h):  # vertical gradient
        shade = int(18 + 22 * (i / h))
        draw.line([(0, i), (w, i)], fill=(color[0] + shade, color[1] + shade, color[2] + shade))
    words, line, lines = text.split(), "", []
    for word in words:
        if len(line + " " + word) > 16:
            lines.append(line.strip())
            line = word
        else:
            line += " " + word
    lines.append(line.strip())
    y = h // 2 - len(lines) * 18
    for ln in lines:
        draw.text((w // 2, y), ln, fill=(235, 235, 245), anchor="mm")
        y += 40
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="JPEG", quality=85)
