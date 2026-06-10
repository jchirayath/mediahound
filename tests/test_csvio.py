"""CSV bulk import → catalog → export round-trip (offline)."""
from mediahound.config import DEFAULTS, Config, _deep_merge
from mediahound.csvio import _row_to_item, export_csv, import_csv
from mediahound.store import Store


def _cfg(tmp_path):
    cfg = Config(_deep_merge(DEFAULTS, {"paths": {"input": "RawImages", "output": "."}}), tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def test_row_to_item_infers_media_type():
    music = _row_to_item({"title": "Abbey Road", "artist": "The Beatles", "year": "1969",
                          "format": "Vinyl", "genres": "Rock; Pop"})
    assert music["media_type"] == "music" and music["artist"] == "The Beatles"
    assert music["genres"] == ["Rock", "Pop"] and music["listen"]["providers"]
    movie = _row_to_item({"title": "The Goonies", "director": "Richard Donner",
                          "year": "1985", "format": "VHS"})
    assert movie["media_type"] == "movie" and movie["director"] == "Richard Donner"
    assert _row_to_item({"media_type": "music", "title": "X"})["media_type"] == "music"
    assert _row_to_item({"artist": "x"}) == {}            # no title → skipped


def test_import_export_roundtrip(tmp_path):
    cfg = _cfg(tmp_path)
    csv_in = tmp_path / "in.csv"
    csv_in.write_text(
        "media_type,title,artist,director,year,format,genres\n"
        "music,Abbey Road,The Beatles,,1969,Vinyl,Rock; Pop\n"
        "movie,The Goonies,,Richard Donner,1985,VHS,Adventure\n", encoding="utf-8")
    store = Store(cfg.data_dir)
    added, enriched = import_csv(cfg, store, csv_in, online=False, log=lambda *_: None)
    assert added == 2 and enriched == 0
    store.save()
    assert {m["media_type"] for m in store.collection} == {"movie", "music"}

    out = tmp_path / "out.csv"
    assert export_csv(store, out) == 2
    text = out.read_text(encoding="utf-8")
    assert "Abbey Road" in text and "The Goonies" in text and text.startswith("media_type,")
