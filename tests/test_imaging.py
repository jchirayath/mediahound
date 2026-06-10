"""Image helpers: rotation, portrait thumbnails, placeholder posters, prepared JPEG."""
from PIL import Image

from reelshelf.imaging import (
    make_placeholder_poster,
    prepared_jpeg,
    rotate_file,
    save_thumbnail,
)
from tests.conftest import make_image


def test_rotate_file_swaps_dimensions_and_noops_on_zero(tmp_path):
    p = make_image(tmp_path / "x.jpg", 200, 100)
    assert rotate_file(p, 90) is True
    with Image.open(p) as im:
        assert (im.width, im.height) == (100, 200)
    assert rotate_file(p, 0) is False                 # no-op
    assert rotate_file(tmp_path / "missing.jpg", 90) is False


def test_save_thumbnail_forces_portrait(tmp_path):
    src = make_image(tmp_path / "land.jpg", 300, 150)  # landscape
    dest = tmp_path / "thumb.jpg"
    save_thumbnail(src, dest, max_edge=120, portrait=True)
    with Image.open(dest) as im:
        assert im.height >= im.width                   # rotated upright
        assert max(im.width, im.height) <= 120


def test_make_placeholder_poster_writes_file(tmp_path):
    dest = tmp_path / "p.jpg"
    make_placeholder_poster("Hello World", dest, subtitle="1999")
    assert dest.is_file() and dest.stat().st_size > 0
    with Image.open(dest) as im:
        assert im.format == "JPEG"


def test_prepared_jpeg_downscales_to_bytes(tmp_path):
    b = prepared_jpeg(make_image(tmp_path / "big.jpg", 2000, 2000), max_edge=256)
    assert isinstance(b, bytes) and b[:2] == b"\xff\xd8"  # JPEG SOI marker
    with Image.open(__import__("io").BytesIO(b)) as im:
        assert max(im.width, im.height) <= 256
