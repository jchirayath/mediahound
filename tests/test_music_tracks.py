"""Album track-info — providers capture tracklists, CSV round-trips them, mock albums have songs."""
import csv
import json

from mediahound import cli
from mediahound.config import load_config
from mediahound.csvio import _row_to_item, export_csv, import_csv
from mediahound.store import Store


def test_mock_albums_have_tracklists(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    coll = json.loads((site / "data" / "collection.json").read_text())
    music = [m for m in coll if m.get("media_type") == "music"]
    assert music and all(m.get("tracklist") for m in music)   # every demo album lists its songs
    dsotm = next(m for m in music if m["title"].startswith("The Dark Side"))
    assert "Money" in dsotm["tracklist"]


def test_csv_import_captures_tracklist():
    item = _row_to_item({"media_type": "music", "title": "Rumours", "artist": "Fleetwood Mac",
                         "year": "1977", "tracklist": "Dreams; The Chain; Go Your Own Way"})
    assert item["media_type"] == "music"
    assert item["tracklist"] == ["Dreams", "The Chain", "Go Your Own Way"]


def test_csv_export_roundtrips_tracklist(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    store.upsert_movie({"id": "a1", "media_type": "music", "title": "Thriller",
                        "artist": "Michael Jackson", "year": 1982,
                        "tracklist": ["Thriller", "Beat It", "Billie Jean"]})
    out = tmp_path / "x.csv"
    export_csv(store, out)
    row = next(r for r in csv.DictReader(out.open()) if r["title"] == "Thriller")
    assert row["tracklist"] == "Thriller; Beat It; Billie Jean"      # songs survive export

    # …and re-import restores the list
    store2 = Store(tmp_path / "site2" / "data")
    import_csv(cfg, store2, out, online=False, log=lambda *_: None)
    again = next(m for m in store2.collection if m["title"] == "Thriller")
    assert again["tracklist"] == ["Thriller", "Beat It", "Billie Jean"]


def test_providers_return_tracklists():
    # both music providers expose a tracklist field on their parsed result
    from mediahound.metadata.base import MusicMeta
    assert "tracklist" in MusicMeta.__dataclass_fields__
