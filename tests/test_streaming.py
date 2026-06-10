"""Where-to-watch (JustWatch) parsing + ranking + graceful failure (mocked HTTP)."""
import requests

import reelshelf.streaming as sx
from tests.conftest import FakeResp


def _edges(offers):
    return {"data": {"popularTitles": {"edges": [
        {"node": {"objectType": "MOVIE",
                  "content": {"title": "X", "originalReleaseYear": 2000},
                  "offers": offers}}
    ]}}}


def test_picks_best_offer_and_only_target_services(monkeypatch):
    offers = [
        {"monetizationType": "BUY", "package": {"clearName": "Netflix"}, "standardWebURL": "https://nf/buy"},
        {"monetizationType": "FLATRATE", "package": {"clearName": "Netflix"}, "standardWebURL": "https://nf/sub"},
        {"monetizationType": "RENT", "package": {"clearName": "Hulu"}, "standardWebURL": "https://hulu/rent"},
        {"monetizationType": "FLATRATE", "package": {"clearName": "SomeOther"}, "standardWebURL": "https://x"},
    ]
    monkeypatch.setattr(sx.requests, "post", lambda *a, **k: FakeResp(_edges(offers)))
    out = sx.fetch_offers("X", 2000)
    assert out["checked"] is True
    provs = {p["name"]: p for p in out["providers"]}
    assert provs["Netflix"]["type"] == "FLATRATE" and provs["Netflix"]["url"] == "https://nf/sub"
    assert "Hulu" in provs and "SomeOther" not in provs  # non-target dropped
    assert out["providers"][0]["name"] == "Netflix"      # FLATRATE ranks before Hulu's RENT
    assert all("_rank" not in p for p in out["providers"])  # internal key stripped


def test_no_offers_still_checked(monkeypatch):
    monkeypatch.setattr(sx.requests, "post", lambda *a, **k: FakeResp(_edges([])))
    out = sx.fetch_offers("X")
    assert out["checked"] is True and out["providers"] == []


def test_graceful_on_network_error(monkeypatch):
    def boom(*a, **k):
        raise requests.Timeout("slow")

    monkeypatch.setattr(sx.requests, "post", boom)
    out = sx.fetch_offers("X")
    assert out["checked"] is False and out["providers"] == []
    assert "justwatch.com" in out["justwatch_url"]


def test_empty_title_short_circuits():
    out = sx.fetch_offers("")
    assert out["checked"] is False
