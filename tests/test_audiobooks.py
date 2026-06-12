"""Audiobooks media type — Open Library + LibriVox provider, mock/CSV/move, where-to-listen links."""
import json

from mediahound import cli
from mediahound.config import load_config
from mediahound.links import hear_links
from mediahound.metadata import get_metadata_provider
from mediahound.metadata.audiobook import AudiobookProvider
from mediahound.store import Store
from tests.conftest import FakeResp

# Open Library search.json shape (reused from the book provider)
_OL = {"docs": [{"title": "Project Hail Mary", "author_name": ["Andy Weir"],
                 "first_publish_year": 2021, "cover_i": 99, "isbn": ["9780593135204"],
                 "publisher": ["Audible Studios"], "subject": ["Science Fiction"],
                 "key": "/works/OL1W"}]}
# LibriVox audiobooks feed shape
_LV = {"books": [{"id": "123", "title": "Project Hail Mary", "totaltimesecs": 58200,
                  "description": "A lone astronaut wakes with no memory.", "copyright_year": "2021",
                  "url_librivox": "https://librivox.org/x"}]}


def _provider(monkeypatch, ol=_OL, lv=_LV):
    p = AudiobookProvider()
    monkeypatch.setattr(p.books.session, "get", lambda url, **k: FakeResp(ol))
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp(lv))
    return p


def test_audiobook_merges_openlibrary_and_librivox(monkeypatch):
    m = _provider(monkeypatch).lookup("Project Hail Mary", narrator="Ray Porter")
    assert m.matched and m.media_type == "audiobook"
    assert m.title == "Project Hail Mary" and m.author == "Andy Weir"
    assert m.narrator == "Ray Porter"                       # passed through (cover/manual)
    assert m.publisher == "Audible Studios" and m.isbn == "9780593135204"
    assert m.duration == 970                                # 58200s / 60 → minutes
    assert m.overview and m.source == "openlibrary+librivox"
    assert m.cover_url


def test_audiobook_matches_with_only_openlibrary(monkeypatch):
    # LibriVox 404s (commercial title) → still a match from Open Library, no duration
    p = AudiobookProvider()
    monkeypatch.setattr(p.books.session, "get", lambda url, **k: FakeResp(_OL))
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp({}, status=404))
    m = p.lookup("Project Hail Mary")
    assert m.matched and m.duration is None and m.source == "openlibrary"


def test_audiobook_no_match(monkeypatch):
    p = AudiobookProvider()
    monkeypatch.setattr(p.books.session, "get", lambda url, **k: FakeResp({"docs": []}))
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp({}, status=404))
    assert p.lookup("Nope").matched is False
    assert p.lookup("").matched is False


def test_provider_registry_returns_audiobook_provider():
    class _C:
        data = {"audiobook": {"metadata": {"provider": "openlibrary"}}}
    assert isinstance(get_metadata_provider(_C(), "audiobook"), AudiobookProvider)


def test_hear_links_target_audiobook_stores():
    names = [p["name"] for p in hear_links("Andy Weir", "Project Hail Mary")["providers"]]
    assert names == ["Audible", "Libro.fm", "LibriVox", "Open Library"]


def test_mock_build_has_audiobooks(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    coll = json.loads((site / "data" / "collection.json").read_text())
    abooks = [m for m in coll if m.get("media_type") == "audiobook"]
    assert len(abooks) == 3
    noah = next(a for a in abooks if a["author"] == "Trevor Noah")
    assert noah["narrator"] == "Trevor Noah" and noah["duration"] == 534
    assert noah["listen"]["providers"]                       # where-to-listen links present


def test_init_creates_audiobooks_folder(tmp_path):
    site = tmp_path / "s"
    cli.main(["init", str(site)])
    assert (site / "RawImages" / "audiobooks").is_dir()


def test_csv_imports_an_audiobook(tmp_path):
    from mediahound.csvio import import_csv
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    csv_path = tmp_path / "a.csv"
    csv_path.write_text("media_type,title,author,narrator,year,format,publisher,duration\n"
                        "audiobook,Educated,Tara Westover,Julia Whelan,2018,Audible,Random House,765\n")
    import_csv(cfg, store, csv_path, online=False, log=lambda *_: None)
    ed = next(m for m in store.collection if m["title"] == "Educated")
    assert ed["media_type"] == "audiobook" and ed["narrator"] == "Julia Whelan"
    assert ed["duration"] == 765 and ed["format"] == "Audible"
    assert ed["listen"]["providers"]


def test_csv_infers_audiobook_from_narrator(tmp_path):
    from mediahound.csvio import _row_to_item
    item = _row_to_item({"title": "X", "author": "A", "narrator": "N", "year": "2020"})
    assert item["media_type"] == "audiobook" and item["narrator"] == "N"


def test_move_to_audiobook_clears_other_fields_keeps_shared(tmp_path):
    """movie→audiobook clears movie-only fields; book→audiobook keeps shared author/publisher/isbn."""
    from mediahound import pipeline
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    store.upsert_movie({"id": "b1", "media_type": "book", "title": "Educated", "author": "Tara Westover",
                        "publisher": "Random House", "isbn": "9780399590504", "page_count": 334,
                        "format": "Hardcover"})
    store.corrections = {"b1": {"media_type": "audiobook", "narrator": "Julia Whelan"}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    m = store.find_movie("b1")
    assert m["media_type"] == "audiobook" and m["narrator"] == "Julia Whelan"
    assert m["author"] == "Tara Westover" and m["publisher"] == "Random House"   # shared kept
    assert m["isbn"] == "9780399590504"
    assert "page_count" not in m                            # book-only field cleared
    assert m["format"] == "Audible"                         # Hardcover → audiobook default
