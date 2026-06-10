"""MusicBrainz provider parsing + keyless listen links (mocked HTTP, no network/sleep)."""
import mediahound.metadata.musicbrainz as mbmod
from mediahound.links import listen_links
from mediahound.metadata.musicbrainz import MusicBrainzProvider
from tests.conftest import FakeResp

_SEARCH = {"releases": [{"id": "abc-123", "title": "Rumours"}]}
_DETAIL = {
    "title": "Rumours",
    "artist-credit": [{"name": "Fleetwood Mac", "joinphrase": ""}],
    "date": "1977-02-04",
    "barcode": "0075992736428",
    "label-info": [{"label": {"name": "Warner Bros. Records"}, "catalog-number": "BSK 3010"}],
    "media": [{"format": "Vinyl", "tracks": [{"title": "Second Hand News"}, {"title": "Dreams"}]}],
    "genres": [{"name": "rock", "count": 5}, {"name": "soft rock", "count": 3}],
}


def test_musicbrainz_parses(monkeypatch):
    monkeypatch.setattr(mbmod.time, "sleep", lambda *_: None)   # skip the 1 req/s politeness wait
    p = MusicBrainzProvider()
    monkeypatch.setattr(p.session, "get",
                        lambda url, **k: FakeResp(_SEARCH if url.endswith("/release") else _DETAIL))
    m = p.lookup("Rumours", artist="Fleetwood Mac")
    assert m.matched and m.media_type == "music" and m.source == "musicbrainz"
    assert m.title == "Rumours" and m.artist == "Fleetwood Mac" and m.year == 1977
    assert m.label == "Warner Bros. Records" and m.catalog_no == "BSK 3010"
    assert m.format == "Vinyl" and m.barcode == "0075992736428"
    assert "Dreams" in m.tracklist and m.genres[0] == "rock"
    assert m.cover_url.endswith("/release/abc-123/front-500")
    assert m.source_url == "https://musicbrainz.org/release/abc-123"


def test_musicbrainz_no_match(monkeypatch):
    monkeypatch.setattr(mbmod.time, "sleep", lambda *_: None)
    p = MusicBrainzProvider()
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp({"releases": []}))
    assert p.lookup("Nope").matched is False
    assert p.lookup("").matched is False


def test_listen_links():
    out = listen_links("Pink Floyd", "The Dark Side of the Moon")
    assert out["checked"] is True
    assert [p["name"] for p in out["providers"]] == ["Spotify", "Apple Music", "YouTube Music"]
    sp = out["providers"][0]
    assert sp["url"].startswith("https://open.spotify.com/search/")
    assert "Pink%20Floyd" in sp["url"]
