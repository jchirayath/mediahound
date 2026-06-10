"""OMDb provider: parsing + graceful degradation (mocked HTTP, no network)."""
import pytest
import requests

import mediahound.metadata.omdb as omod
from mediahound.metadata.omdb import OMDBProvider
from tests.conftest import FakeResp

_PAYLOAD = {
    "Response": "True", "Title": "Blade Runner", "Year": "1982", "imdbID": "tt0083658",
    "Genre": "Sci-Fi, Thriller", "Director": "Ridley Scott",
    "Actors": "Harrison Ford, Rutger Hauer, Sean Young", "Production": "Warner Bros.",
    "imdbRating": "8.1", "Runtime": "117 min", "Language": "English, German",
    "Plot": "A blade runner hunts replicants.", "Poster": "https://img/x.jpg",
}


def test_omdb_parses_full_payload(monkeypatch):
    monkeypatch.setenv("OMDB_API_KEY", "k")
    monkeypatch.setattr(omod.requests, "get", lambda *a, **k: FakeResp(_PAYLOAD))
    m = OMDBProvider({}).lookup("Blade Runner", 1982)
    assert m.matched and m.source == "omdb" and m.source_id == "tt0083658"
    assert m.title == "Blade Runner" and m.year == 1982
    assert m.rating == 8.1 and m.runtime == 117 and m.director == "Ridley Scott"
    assert m.genres == ["Sci-Fi", "Thriller"]
    assert "Harrison Ford" in m.actors and len(m.actors) == 3
    assert m.studio == "Warner Bros." and m.language == "English"
    assert m.spoken_languages == ["English", "German"]
    assert m.poster_url == "https://img/x.jpg"
    assert m.source_url == "https://www.imdb.com/title/tt0083658/"


def test_omdb_handles_na_and_missing_fields(monkeypatch):
    monkeypatch.setenv("OMDB_API_KEY", "k")
    payload = {"Response": "True", "Title": "Tape", "Year": "1990", "imdbID": "tt1",
               "imdbRating": "N/A", "Runtime": "N/A", "Director": "N/A",
               "Actors": "N/A", "Production": "N/A", "Poster": "N/A", "Genre": ""}
    monkeypatch.setattr(omod.requests, "get", lambda *a, **k: FakeResp(payload))
    m = OMDBProvider({}).lookup("Tape")
    assert m.matched
    assert m.rating is None and m.runtime is None and m.director is None
    assert m.actors == [] and m.studio is None and m.poster_url is None and m.genres == []


def test_omdb_quota_or_no_match_is_not_fatal(monkeypatch):
    monkeypatch.setenv("OMDB_API_KEY", "k")
    p = OMDBProvider({})
    monkeypatch.setattr(omod.requests, "get",
                        lambda *a, **k: FakeResp({"Response": "False", "Error": "Request limit reached!"}))
    assert p.lookup("X", 1).matched is False


def test_omdb_network_error_is_not_fatal(monkeypatch):
    monkeypatch.setenv("OMDB_API_KEY", "k")
    p = OMDBProvider({})

    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(omod.requests, "get", boom)
    assert p.lookup("X", 1).matched is False
    assert p.lookup("", 1).matched is False  # empty title short-circuits


def test_omdb_requires_key(monkeypatch):
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OMDBProvider({})
