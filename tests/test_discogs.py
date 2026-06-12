"""Feature 02 — Discogs metadata provider, collection import, and price suggestions."""
import mediahound.discogs_import as di
import mediahound.metadata.discogs as dz
from mediahound import resale
from mediahound.metadata import get_metadata_provider
from mediahound.metadata.discogs import DiscogsProvider
from tests.conftest import FakeResp

_SEARCH = {"results": [{"id": 249504}]}
_RELEASE = {
    "title": "Rumours", "artists": [{"name": "Fleetwood Mac (2)"}], "year": 1977,
    "labels": [{"name": "Warner Bros. Records", "catno": "BSK 3010"}],
    "formats": [{"name": "Vinyl", "qty": "1", "descriptions": ["LP", "Album"]}],
    "genres": ["Rock"], "styles": ["Soft Rock"],
    "tracklist": [{"title": "Dreams", "type_": "track"}, {"title": "(side b)", "type_": "heading"}],
    "identifiers": [{"type": "Barcode", "value": "0 7599 27313 1"}],
    "images": [{"type": "primary", "uri": "http://img/cover.jpg"}],
    "community": {"rating": {"average": 4.5}},
    "uri": "https://www.discogs.com/release/249504",
}


def _provider(monkeypatch, search=_SEARCH, release=_RELEASE):
    monkeypatch.setattr(dz.time, "sleep", lambda *_: None)
    p = DiscogsProvider()
    monkeypatch.setattr(p.session, "get",
                        lambda url, **k: FakeResp(search if "/database/search" in url else release))
    return p


def test_discogs_lookup_parses(monkeypatch):
    p = _provider(monkeypatch)
    m = p.lookup("Rumours", artist="Fleetwood Mac")
    assert m.matched and m.source == "discogs" and m.source_id == "249504"
    assert m.artist == "Fleetwood Mac"              # "(2)" disambiguator stripped
    assert m.year == 1977 and m.format == "Vinyl"
    assert m.label == "Warner Bros. Records" and m.catalog_no == "BSK 3010"
    assert m.barcode == "07599273131"               # spaces removed
    assert m.genres == ["Rock", "Soft Rock"]
    assert m.tracklist == ["Dreams"]                # heading rows dropped
    assert m.rating == 9.0                          # 4.5/5 → /10 scale
    assert m.cover_url == "http://img/cover.jpg"


def test_discogs_lookup_by_barcode(monkeypatch):
    p = _provider(monkeypatch)
    m = p.lookup_by_barcode("0075992731317")
    assert m.matched and m.title == "Rumours"


def test_discogs_no_match(monkeypatch):
    p = _provider(monkeypatch, search={"results": []})
    assert p.lookup("Nope").matched is False
    assert p.lookup_by_barcode("000").matched is False
    assert p.lookup("").matched is False


def test_price_suggestion_requires_token(monkeypatch):
    p = _provider(monkeypatch)                       # no token
    assert p.price_suggestion("249504") is None
    p.token = "tok"
    monkeypatch.setattr(p.session, "get",
                        lambda url, **k: FakeResp({"Very Good Plus (VG+)": {"value": 24.5, "currency": "USD"}}))
    info = p.price_suggestion("249504")
    assert info == {"value": 24.5, "currency": "USD"}


def test_resale_discogs_price_wrapper(monkeypatch):
    monkeypatch.setattr(DiscogsProvider, "price_suggestion",
                        lambda self, rid, cond="Very Good Plus (VG+)": {"value": 30.0, "currency": "USD"})
    out = resale.discogs_price("249504", token="tok")
    assert out["mid"] == 30.0 and out["currency"] == "USD"
    assert out["discogs_release_id"] == "249504" and "Discogs" in out["note"]


def test_get_metadata_provider_selects_discogs():
    class Cfg:
        data = {"music": {"metadata": {"provider": "discogs"}}}
    prov = get_metadata_provider(Cfg(), "music")
    assert isinstance(prov, DiscogsProvider)


# -- collection import ----------------------------------------------------
class _FakeSession:
    def __init__(self, page_body):
        self.headers = {}
        self._body = page_body

    def get(self, url, params=None, timeout=None):
        return FakeResp(self._body)


def test_import_collection_offline(monkeypatch, tmp_path):
    from mediahound import cli
    from mediahound.config import load_config
    from mediahound.store import Store
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")

    collection = {"pagination": {"pages": 1}, "releases": [
        {"basic_information": {"id": 249504, "title": "Rumours",
                               "artists": [{"name": "Fleetwood Mac (2)"}], "year": 1977,
                               "labels": [{"name": "Warner Bros.", "catno": "BSK 3010"}],
                               "formats": [{"name": "Vinyl"}], "genres": ["Rock"], "styles": ["Soft Rock"],
                               "cover_image": "http://img/c.jpg"}}]}
    monkeypatch.setattr(di.time, "sleep", lambda *_: None)
    monkeypatch.setattr(di.requests, "Session", lambda: _FakeSession(collection))

    store = Store(cfg.data_dir)
    added, enriched = di.import_collection(cfg, store, "someuser", online=False, log=lambda *_: None)
    assert added == 1 and enriched == 0
    item = next(m for m in store.collection if m.get("source", {}).get("name") == "discogs")
    assert item["title"] == "Rumours" and item["artist"] == "Fleetwood Mac"   # "(2)" stripped
    assert item["media_type"] == "music" and item["format"] == "Vinyl"
    assert item["discogs_release_id"] == "249504"


def test_import_collection_missing_user(monkeypatch, tmp_path):
    from mediahound import cli
    from mediahound.config import load_config
    from mediahound.store import Store
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")

    class _NotFound:
        headers = {}

        def get(self, url, params=None, timeout=None):
            return FakeResp({}, status=404)
    monkeypatch.setattr(di.time, "sleep", lambda *_: None)
    monkeypatch.setattr(di.requests, "Session", lambda: _NotFound())
    import pytest
    with pytest.raises(RuntimeError):
        di.import_collection(cfg, Store(cfg.data_dir), "ghost", online=False, log=lambda *_: None)
