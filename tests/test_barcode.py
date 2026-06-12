"""Feature 01 — barcode decode + UPC/EAN resolution (music & movie) and pipeline wiring."""
import json
import threading
import time
import urllib.request

import mediahound.metadata.musicbrainz as mbmod
from mediahound import barcode, cli
from mediahound.config import load_config
from mediahound.metadata.base import MusicMeta
from mediahound.metadata.upcitemdb import UPCItemDBProvider, clean_title
from tests.conftest import FakeResp, make_image

_MB_SEARCH = {"releases": [{"id": "rid-1"}]}
_MB_DETAIL = {"title": "Rumours", "date": "1977", "artist-credit": [{"name": "Fleetwood Mac", "joinphrase": ""}],
              "media": [{"format": "Vinyl", "tracks": [{"title": "Dreams"}]}], "barcode": "0075992736428"}


# -- MusicBrainz barcode search ------------------------------------------
def test_musicbrainz_lookup_by_barcode(monkeypatch):
    monkeypatch.setattr(mbmod.time, "sleep", lambda *_: None)
    p = mbmod.MusicBrainzProvider()
    monkeypatch.setattr(p.session, "get",
                        lambda url, **k: FakeResp(_MB_SEARCH if url.endswith("/release") else _MB_DETAIL))
    m = p.lookup_by_barcode("0075992736428")
    assert m.matched and m.title == "Rumours" and m.barcode == "0075992736428"
    assert p.lookup_by_barcode("").matched is False


# -- UPCItemDB (movies) --------------------------------------------------
def test_clean_title_strips_edition_noise():
    assert clean_title("The Matrix (Blu-ray) [Widescreen] 2-Disc Special Edition") == "The Matrix"
    assert clean_title("Coco DVD") == "Coco"
    assert clean_title("") is None


def test_upcitemdb_title_for(monkeypatch):
    p = UPCItemDBProvider()
    monkeypatch.setattr(p.session, "get",
                        lambda url, **k: FakeResp({"items": [{"title": "Blade Runner (4K UHD)"}]}))
    assert p.title_for("123456789012") == "Blade Runner"
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp({"items": []}))
    assert p.title_for("000") is None


# -- decode_image is graceful when the optional decoder is absent --------
def test_decode_image_never_raises(tmp_path):
    img = make_image(tmp_path / "x.jpg", 60, 60)
    out = barcode.decode_image(img)
    assert isinstance(out, list)            # [] if zxing-cpp isn't installed, else any codes


# -- barcode.lookup routing ----------------------------------------------
class _FakeMusicProv:
    def lookup_by_barcode(self, upc, year=None):
        return MusicMeta(True, source="musicbrainz", title="Kind of Blue", artist="Miles Davis",
                         year=1959, format="Vinyl", cover_url=None,
                         source_url="https://musicbrainz.org/release/x")


def test_lookup_music(monkeypatch):
    monkeypatch.setattr(barcode, "_music_provider", lambda cfg: _FakeMusicProv())
    out = barcode.lookup(None, "0123456789012", "music")
    assert out["media_type"] == "music" and out["title"] == "Kind of Blue"
    assert out["artist"] == "Miles Davis" and out["meta"].year == 1959


def test_lookup_movie(monkeypatch):
    monkeypatch.setattr(UPCItemDBProvider, "title_for", lambda self, upc: "The Matrix")
    out = barcode.lookup(None, "0123456789012", "movie")
    assert out == {"media_type": "movie", "upc": "0123456789012", "title": "The Matrix", "year": None}


def test_lookup_empty_upc():
    assert barcode.lookup(None, "", "music") is None


# -- music_item_from_meta -------------------------------------------------
def test_music_item_from_meta(tmp_path):
    site = tmp_path / "s"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")
    meta = MusicMeta(True, source="discogs", source_id="9", title="Thriller", artist="Michael Jackson",
                     year=1982, format="Vinyl", label="Epic", cover_url="http://img/c.jpg",
                     tracklist=["Beat It"], raw={"release_id": "9"})
    item = barcode.music_item_from_meta(cfg, meta, "0123456789012")
    assert item["media_type"] == "music" and item["title"] == "Thriller"
    assert item["barcode"] == "0123456789012" and item["discogs_release_id"] == "9"
    assert item["poster"] == "http://img/c.jpg" and item["resale"]["sold_listings_url"]


# -- pipeline integration: a music barcode writes the exact release -------
def test_pipeline_prefers_barcode_for_music(monkeypatch, tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg_file = site / "config.toml"
    cfg_file.write_text(cfg_file.read_text().replace("enabled  = true", "enabled  = false"))  # no JustWatch net
    cfg = load_config(cfg_file)
    make_image(cfg.input_dir / "audio" / "cover.jpg", 80, 80)

    meta = MusicMeta(True, source="discogs", title="Nevermind", artist="Nirvana", year=1991,
                     format="CD", cover_url=None, source_url="https://www.discogs.com/release/1")
    monkeypatch.setattr(barcode, "decode_image", lambda p: ["0123456789012"])
    monkeypatch.setattr(barcode, "lookup", lambda cfg, upc, mt: {
        "media_type": "music", "upc": upc, "title": meta.title, "artist": meta.artist,
        "year": meta.year, "meta": meta})

    from mediahound import pipeline
    pipeline.build(cfg, online=True, log=lambda *_: None)
    coll = json.loads((cfg.data_dir / "collection.json").read_text())
    item = next(m for m in coll if m["title"] == "Nevermind")
    assert item["artist"] == "Nirvana" and item["media_type"] == "music"
    assert item["source"]["name"] == "discogs"     # came from the barcode-pinned release, not OCR


# -- /api/identify-barcode ------------------------------------------------
def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_api_identify_barcode_adds_music(monkeypatch, tmp_path):
    from mediahound import serve
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")

    meta = MusicMeta(True, source="musicbrainz", title="Rumours", artist="Fleetwood Mac",
                     year=1977, format="Vinyl", cover_url=None, source_url="https://mb/x")
    monkeypatch.setattr("mediahound.barcode.lookup", lambda cfg, upc, mt: {
        "media_type": "music", "upc": upc, "title": meta.title, "artist": meta.artist,
        "year": meta.year, "meta": meta})

    port = _free_port()
    threading.Thread(target=serve.serve, daemon=True,
                     kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=True,
                                 open_browser=False, log=lambda *_: None)).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read()
            break
        except OSError:
            time.sleep(0.05)
    req = urllib.request.Request(base + "/api/identify-barcode",
                                 data=json.dumps({"upc": "0075992736428", "media_type": "music"}).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json", "Origin": base})
    with urllib.request.urlopen(req, timeout=4) as r:
        body = json.loads(r.read())
    assert body["ok"] and body["matched"] and body["title"] == "Rumours"
    assert any(m["title"] == "Rumours" for m in json.loads((cfg.data_dir / "collection.json").read_text()))
