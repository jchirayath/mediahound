"""Pure helpers + security guards in the pipeline (no network)."""
from PIL import Image

from mediahound import pipeline
from mediahound.config import DEFAULTS, Config, _deep_merge
from mediahound.pipeline import (
    _download_poster,
    _NullMetadata,
    _plausible_title,
    _sig_tokens,
    _slug,
)
from mediahound.store import Store
from tests.conftest import make_image


def test_plausible_title_guard():
    assert _plausible_title("The Matrix", "Matrix") is True
    assert _plausible_title("Serenity", "Serenity") is True
    assert _plausible_title("Coco", "Frozen") is False        # different film → reject
    assert _plausible_title("", "x") is False
    assert _plausible_title("x", "") is False


def test_slug_and_significant_tokens():
    assert _slug("The Lord of the Rings!") == "the-lord-of-the-rings"
    assert _slug("   ") == "item"
    toks = _sig_tokens("The Lord of the Rings")
    assert "rings" in toks and "lord" in toks and "the" not in toks  # stopwords dropped


def test_download_poster_rejects_non_http_schemes(tmp_path):
    dest = tmp_path / "x.jpg"
    assert _download_poster("file:///etc/passwd", dest) is False
    assert _download_poster("javascript:alert(1)", dest) is False
    assert _download_poster(None, dest) is False
    assert not dest.exists()  # nothing was written / fetched


def test_null_metadata_is_offline():
    m = _NullMetadata().lookup("Anything", 2000)
    assert m.matched is False


def _cfg(tmp_path):
    cfg = Config(_deep_merge(DEFAULTS, {"paths": {"input": "RawImages", "output": "site"}}), tmp_path)
    (cfg.output_dir / "data").mkdir(parents=True, exist_ok=True)
    return cfg


def test_rotation_correction_blocks_path_traversal(tmp_path):
    outside = make_image(tmp_path / "secret.jpg", 40, 40, (9, 9, 9))  # OUTSIDE the site
    before = outside.read_bytes()
    cfg = _cfg(tmp_path)
    store = Store(cfg.output_dir / "data")
    store.upsert_movie({"id": "m1", "title": "A", "images": ["posters/m1.jpg"]})
    store.corrections = {"m1": {"rotations": {"../../secret.jpg": 90}}}
    logs = []
    pipeline._apply_corrections(cfg, store, logs.append, online=False)
    assert outside.read_bytes() == before                         # untouched
    assert any("unsafe" in m for m in logs)


def test_rotation_correction_applies_inside_posters(tmp_path):
    cfg = _cfg(tmp_path)
    posters = cfg.output_dir / "posters"
    posters.mkdir(parents=True)
    make_image(posters / "m1.jpg", 200, 100)
    store = Store(cfg.output_dir / "data")
    store.upsert_movie({"id": "m1", "title": "A", "images": ["posters/m1.jpg"]})
    store.corrections = {"m1": {"rotations": {"posters/m1.jpg": 90}}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    with Image.open(posters / "m1.jpg") as im:
        assert (im.width, im.height) == (100, 200)                # rotated in place


def test_delete_correction_removes_title(tmp_path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.output_dir / "data")
    store.upsert_movie({"id": "m1", "title": "A", "images": ["x"]})
    store.corrections = {"m1": {"delete": True}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    assert store.find_movie("m1") is None


def test_media_type_move_movie_to_music_clears_movie_fields(tmp_path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.output_dir / "data")
    store.upsert_movie({"id": "m1", "media_type": "movie", "title": "Live Concert",
                        "director": "X", "actors": ["Y"], "studio": "Z",
                        "streaming": {"providers": []}, "images": ["x"]})
    store.corrections = {"m1": {"media_type": "music", "artist": "The Band"}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    m = store.find_movie("m1")
    assert m["media_type"] == "music"
    assert m["artist"] == "The Band"
    for gone in ("director", "actors", "studio", "streaming"):
        assert gone not in m                       # movie-only fields cleared


def test_media_type_move_music_to_movie_clears_music_fields(tmp_path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.output_dir / "data")
    store.upsert_movie({"id": "m1", "media_type": "music", "title": "Not Music",
                        "artist": "A", "label": "L", "tracklist": ["t1"], "images": ["x"]})
    store.corrections = {"m1": {"media_type": "movie", "studio": "Studio"}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    m = store.find_movie("m1")
    assert m["media_type"] == "movie"
    assert m["studio"] == "Studio"
    for gone in ("artist", "label", "tracklist"):
        assert gone not in m                       # music-only fields cleared
