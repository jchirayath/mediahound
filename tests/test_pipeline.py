"""Offline smoke tests — no network, no keys (mock pipeline + helpers)."""
import json
from pathlib import Path

from reelshelf.config import Config, DEFAULTS, _deep_merge
from reelshelf import pipeline
from reelshelf.resale import estimate
from reelshelf.intro import make_intro
from reelshelf.identify.base import Identification
from reelshelf.metadata.base import MovieMeta


def _cfg(tmp_path: Path) -> Config:
    data = _deep_merge(DEFAULTS, {"paths": {"input": "RawImages", "output": "."}})
    return Config(data, tmp_path)


def test_mock_build_writes_catalog(tmp_path):
    (tmp_path / "RawImages").mkdir()
    cfg = _cfg(tmp_path)
    stats = pipeline.build(cfg, mock=True, log=lambda *_: None)

    collection = json.loads((tmp_path / "data" / "collection.json").read_text())
    assert len(collection) == stats.identified >= 5
    first = collection[0]
    for key in ("id", "title", "year", "format", "intro", "resale", "seen", "images"):
        assert key in first
    # the rich demo exercises every card field somewhere
    assert any(m.get("director") for m in collection)
    assert any(m.get("actors") for m in collection)
    assert any(m.get("studio") for m in collection)
    assert any(m.get("streaming", {}).get("providers") for m in collection if m.get("streaming"))
    assert any(len(m.get("images", [])) > 1 for m in collection)  # a multi-photo gallery
    # generated site files
    assert (tmp_path / "data" / "site.json").is_file()
    assert (tmp_path / "data" / "view-config.json").is_file()
    assert (tmp_path / "data" / "bundle.js").is_file()
    assert any((tmp_path / "posters").glob("*.jpg"))
    # sample unidentified items exist
    unid = json.loads((tmp_path / "data" / "unidentified.json").read_text())
    assert len(unid) >= 1


def test_incremental_is_idempotent(tmp_path):
    (tmp_path / "RawImages").mkdir()
    cfg = _cfg(tmp_path)
    pipeline.build(cfg, mock=True, log=lambda *_: None)
    ids_before = sorted(m["id"] for m in json.loads((tmp_path / "data" / "collection.json").read_text()))
    pipeline.build(cfg, mock=True, log=lambda *_: None)  # rebuild
    ids_after = sorted(m["id"] for m in json.loads((tmp_path / "data" / "collection.json").read_text()))
    assert ids_before == ids_after  # no duplicates on rebuild


def test_resale_estimate_ranges():
    v = estimate("Some Old Tape", 1988, "VHS", 8.0, "com")
    assert v["low"] < v["mid"] < v["high"]
    assert v["sold_listings_url"].startswith("https://www.ebay.com/")
    assert "LH_Sold=1" in v["sold_listings_url"]


def test_intro_prefers_tagline_then_template():
    ident = Identification(True, "Film", 1999, "DVD")
    meta = MovieMeta(True, tagline="One ring to rule them all.", genres=["Fantasy"], year=1999)
    assert make_intro(ident, meta) == "One ring to rule them all."

    meta2 = MovieMeta(True, genres=["Horror"], year=1981)
    out = make_intro(ident, meta2)
    assert out and isinstance(out, str)
