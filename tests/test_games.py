"""Feature 05 (Video games) — Wikidata SPARQL provider, UPC routing, mock/CSV/move handling,
plus the shared media-type registry behaviour (cross-type field clearing keeps shared fields)."""
import json

from mediahound import barcode, cli
from mediahound.config import load_config
from mediahound.links import play_links
from mediahound.metadata import get_metadata_provider
from mediahound.metadata.games import GameProvider, _esc
from mediahound.store import Store
from tests.conftest import FakeResp

_ENT = "http://www.wikidata.org/entity/Q19610114"
# two rows for the same game → multiple platforms must aggregate (Switch + Wii U → [Switch, Retro])
_SPARQL = {"results": {"bindings": [
    {"item": {"value": _ENT}, "itemLabel": {"value": "The Legend of Zelda: Breath of the Wild"},
     "devLabel": {"value": "Nintendo EPD"}, "pubLabel": {"value": "Nintendo"},
     "genreLabel": {"value": "action-adventure game"},
     "platformLabel": {"value": "Nintendo Switch"}, "date": {"value": "2017-03-03T00:00:00Z"},
     "image": {"value": "http://commons.wikimedia.org/special/botw.jpg"}},
    {"item": {"value": _ENT}, "itemLabel": {"value": "The Legend of Zelda: Breath of the Wild"},
     "devLabel": {"value": "Nintendo EPD"}, "pubLabel": {"value": "Nintendo"},
     "genreLabel": {"value": "action-adventure game"},
     "platformLabel": {"value": "Wii U"}, "date": {"value": "2017-03-03T00:00:00Z"}},
]}}


def _provider(monkeypatch, payload=_SPARQL):
    p = GameProvider()
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp(payload))
    return p


def test_wikidata_games_parses(monkeypatch):
    m = _provider(monkeypatch).lookup("The Legend of Zelda: Breath of the Wild")
    assert m.matched and m.media_type == "game" and m.source == "wikidata"
    assert m.title == "The Legend of Zelda: Breath of the Wild"
    assert m.developer == "Nintendo EPD" and m.publisher == "Nintendo" and m.year == 2017
    assert m.format == "Switch" and m.platforms == ["Switch", "Retro"]   # Wii U → Retro bucket
    assert m.genres == ["action-adventure game"]
    assert m.cover_url and m.cover_url.endswith("?width=500")
    assert m.source_id == "Q19610114"


def test_wikidata_games_no_match(monkeypatch):
    p = GameProvider()
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp({"results": {"bindings": []}}))
    assert p.lookup("Nope").matched is False
    assert p.lookup("").matched is False


def test_sparql_escaping_blocks_injection():
    # a title with a quote / backslash / newline must not break out of the SPARQL string literal
    assert _esc('a"b') == 'a\\"b'
    assert _esc("a\\b") == "a\\\\b"
    assert "\n" not in _esc("a\nb") and _esc("a\nb") == "ab"


def test_provider_registry_returns_game_provider():
    cfg = load_config_from_defaults()
    assert isinstance(get_metadata_provider(cfg, "game"), GameProvider)


def load_config_from_defaults():
    class _C:
        data = {"game": {"metadata": {"provider": "wikidata"}}}
    return _C()


# -- UPC barcode routing --------------------------------------------------
def test_game_upc_routes_via_product_title(monkeypatch):
    from mediahound.metadata.upcitemdb import UPCItemDBProvider
    monkeypatch.setattr(UPCItemDBProvider, "title_for", lambda self, upc: "Super Mario Odyssey")
    out = barcode.lookup(None, "045496590741", "game")
    assert out["media_type"] == "game" and out["title"] == "Super Mario Odyssey"


# -- where-to-play links --------------------------------------------------
def test_play_links_pick_storefront_by_platform():
    assert [p["name"] for p in play_links("Halo", "Xbox")["providers"]] == ["Xbox", "MobyGames"]
    assert [p["name"] for p in play_links("Zelda", "Switch")["providers"]] == ["eShop", "MobyGames"]
    assert [p["name"] for p in play_links("Half-Life", "PC")["providers"]] == ["Steam", "MobyGames"]


# -- mock build + folder + CSV + move ------------------------------------
def test_mock_build_has_games(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    coll = json.loads((site / "data" / "collection.json").read_text())
    games = [m for m in coll if m.get("media_type") == "game"]
    assert len(games) == 3
    witcher = next(g for g in games if g["title"].startswith("The Witcher 3"))
    assert witcher["developer"] == "CD Projekt Red" and witcher["format"] == "PC"
    assert witcher["play"]["providers"]                    # where-to-play links present
    assert witcher["resale"].get("price_check_url")        # PriceCharting link present
    assert all(g["images"] and str(g["images"][0]).startswith("http") for g in games)  # real box art


def test_init_creates_games_folder(tmp_path):
    site = tmp_path / "s"
    cli.main(["init", str(site)])
    assert (site / "RawImages" / "games").is_dir()


def test_csv_imports_a_game(tmp_path):
    from mediahound.csvio import import_csv
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    csv_path = tmp_path / "g.csv"
    csv_path.write_text("media_type,title,developer,publisher,year,format,platforms\n"
                        "game,Hollow Knight,Team Cherry,Team Cherry,2017,PC,PC; Switch\n")
    import_csv(cfg, store, csv_path, online=False, log=lambda *_: None)
    hk = next(m for m in store.collection if m["title"] == "Hollow Knight")
    assert hk["media_type"] == "game" and hk["developer"] == "Team Cherry"
    assert hk["format"] == "PC" and hk["platforms"] == ["PC", "Switch"]
    assert hk["play"]["providers"]


def test_move_to_game_clears_other_type_fields(tmp_path):
    from mediahound import pipeline
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    store.upsert_movie({"id": "x1", "media_type": "movie", "title": "Not A Movie",
                        "director": "D", "studio": "S", "actors": ["a"], "format": "DVD"})
    store.corrections = {"x1": {"media_type": "game", "developer": "Real Dev"}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    m = store.find_movie("x1")
    assert m["media_type"] == "game" and m["developer"] == "Real Dev"
    for gone in ("director", "studio", "actors"):
        assert gone not in m                               # movie-only fields cleared
    assert m["format"] == "Switch"                         # DVD normalised to a game format


def test_move_book_to_game_keeps_shared_publisher(tmp_path):
    """publisher is shared by book AND game — moving between them must NOT drop it."""
    from mediahound import pipeline
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    store.upsert_movie({"id": "b1", "media_type": "book", "title": "X", "author": "A",
                        "publisher": "Acme", "format": "Paperback"})
    store.corrections = {"b1": {"media_type": "game"}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    m = store.find_movie("b1")
    assert m["media_type"] == "game"
    assert m["publisher"] == "Acme"                        # shared field preserved across the move
    assert "author" not in m                               # book-only field cleared
