"""Image helpers: prepare a compact JPEG for vision/OCR and save thumbnails."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


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


def make_placeholder_poster(text: str, dest: Path, color=(40, 44, 64), subtitle=None) -> None:
    """A styled placeholder poster used by --mock. Deliberately generated art (never a real
    movie poster) so the demo carries no copyrighted images."""
    import unicodedata
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode() or text
    text = ascii_text
    w, h = 600, 900
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    for i in range(h):  # vertical gradient: a touch lighter at top, darker toward the bottom
        shade = int(30 * (1 - i / h)) - int(22 * (i / h))
        draw.line([(0, i), (w, i)],
                  fill=tuple(max(0, min(255, c + shade)) for c in color))

    # translucent "play" motif up top
    cx, cy, r = w // 2, int(h * 0.33), 112
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 0), width=5)
    draw.polygon([(cx - 36, cy - 56), (cx - 36, cy + 56), (cx + 60, cy)], fill=(255, 255, 255))

    try:
        title_font = ImageFont.load_default(size=58)
        sub_font = ImageFont.load_default(size=30)
    except TypeError:  # very old Pillow without sized default
        title_font = sub_font = ImageFont.load_default()

    # wrap the title to the poster width
    words, line, lines = text.split(), "", []
    for word in words:
        test = (line + " " + word).strip()
        if line and draw.textlength(test, font=title_font) > w - 80:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)

    y = int(h * 0.60)
    for ln in lines:
        draw.text((w // 2, y), ln, font=title_font, fill=(245, 246, 250), anchor="ma")
        y += 66
    if subtitle:
        draw.text((w // 2, y + 10), str(subtitle), font=sub_font, fill=(190, 195, 208), anchor="ma")

    # honest footer: this is generated art, not a real poster (copyright-safe demo)
    try:
        cap_font = ImageFont.load_default(size=20)
    except TypeError:
        cap_font = ImageFont.load_default()
    draw.text((w // 2, h - 28), "placeholder art · not a real poster",
              font=cap_font, fill=(150, 155, 168), anchor="ma")

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="JPEG", quality=88)
