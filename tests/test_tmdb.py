"""TMDB provider: two-call lookup parsing + graceful no-match (mocked HTTP)."""
import pytest

import mediahound.metadata.tmdb as tmod
from mediahound.metadata.tmdb import TMDBProvider
from tests.conftest import FakeResp

_SEARCH = {"results": [{"id": 603, "title": "The Matrix"}]}
_DETAIL = {
    "id": 603, "title": "The Matrix", "original_title": "The Matrix",
    "release_date": "1999-03-31", "genres": [{"name": "Action"}, {"name": "Science Fiction"}],
    "original_language": "en", "spoken_languages": [{"iso_639_1": "en", "english_name": "English"}],
    "runtime": 136, "vote_average": 8.217, "tagline": "Free your mind.",
    "overview": "A hacker discovers reality is a simulation.",
    "poster_path": "/p.jpg", "backdrop_path": "/b.jpg",
    "production_companies": [{"name": "Warner Bros."}],
    "credits": {"cast": [{"name": "Keanu Reeves"}, {"name": "Laurence Fishburne"}],
                "crew": [{"job": "Director", "name": "Lana Wachowski"}]},
}


def test_tmdb_parses_search_then_detail(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "k")

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResp(_SEARCH if "/search/movie" in url else _DETAIL)

    monkeypatch.setattr(tmod.requests, "get", fake_get)
    m = TMDBProvider({}).lookup("The Matrix", 1999)
    assert m.matched and m.source == "tmdb" and m.source_id == "603"
    assert m.title == "The Matrix" and m.year == 1999
    assert m.genres == ["Action", "Science Fiction"]
    assert m.language == "English" and m.runtime == 136
    assert m.rating == 8.2                                  # rounded to 1 dp
    assert m.director == "Lana Wachowski"
    assert m.actors[:2] == ["Keanu Reeves", "Laurence Fishburne"]
    assert m.studio == "Warner Bros." and m.tagline == "Free your mind."
    assert m.poster_url.endswith("/w500/p.jpg")
    assert m.source_url == "https://www.themoviedb.org/movie/603"


def test_tmdb_v4_token_uses_bearer(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "eyJabc.def.ghi")     # v4 read access token (JWT)
    cap = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        cap["headers"], cap["params"] = headers, params
        return FakeResp(_SEARCH if "/search/movie" in url else _DETAIL)

    monkeypatch.setattr(tmod.requests, "get", fake_get)
    TMDBProvider({}).lookup("The Matrix", 1999)
    assert cap["headers"].get("Authorization") == "Bearer eyJabc.def.ghi"
    assert "api_key" not in cap["params"]                    # not sent as a query param


def test_tmdb_v3_key_uses_query_param(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "abc123def")          # classic v3 key
    cap = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        cap["headers"], cap["params"] = headers, params
        return FakeResp(_SEARCH if "/search/movie" in url else _DETAIL)

    monkeypatch.setattr(tmod.requests, "get", fake_get)
    TMDBProvider({}).lookup("The Matrix", 1999)
    assert cap["params"].get("api_key") == "abc123def"
    assert "Authorization" not in cap["headers"]


def test_tmdb_no_results_and_empty_title(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "k")
    monkeypatch.setattr(tmod.requests, "get", lambda *a, **k: FakeResp({"results": []}))
    assert TMDBProvider({}).lookup("Nonexistent Film", 1800).matched is False
    assert TMDBProvider({}).lookup("").matched is False


def test_tmdb_requires_key(monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        TMDBProvider({})
