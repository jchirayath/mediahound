"""Feature 05 (Books) — Open Library provider, ISBN barcode routing, mock/CSV/move handling."""
import json

import mediahound.metadata as meta_mod
from mediahound import barcode, cli
from mediahound.config import load_config
from mediahound.metadata.openlibrary import OpenLibraryProvider
from mediahound.store import Store
from tests.conftest import FakeResp

_SEARCH = {"docs": [{"title": "Dune", "author_name": ["Frank Herbert"], "first_publish_year": 1965,
                     "cover_i": 12345, "isbn": ["9780441172719"], "number_of_pages_median": 688,
                     "publisher": ["Ace"], "subject": ["Science Fiction", "Adventure"],
                     "key": "/works/OL893415W"}]}
_ISBN = {"ISBN:9780441172719": {"title": "Dune", "authors": [{"name": "Frank Herbert"}],
                                "publishers": [{"name": "Ace"}], "publish_date": "1990",
                                "number_of_pages": 688, "cover": {"large": "http://c/dune.jpg"},
                                "subjects": [{"name": "Science Fiction"}],
                                "url": "https://openlibrary.org/books/OL1M"}}


def _provider(monkeypatch):
    p = OpenLibraryProvider()
    monkeypatch.setattr(p.session, "get",
                        lambda url, **k: FakeResp(_SEARCH if "search.json" in url else _ISBN))
    return p


def test_openlibrary_search_parses(monkeypatch):
    m = _provider(monkeypatch).lookup("Dune")
    assert m.matched and m.media_type == "book" and m.source == "openlibrary"
    assert m.title == "Dune" and m.author == "Frank Herbert" and m.year == 1965
    assert m.publisher == "Ace" and m.page_count == 688
    assert m.genres == ["Science Fiction", "Adventure"] and m.cover_url
    assert m.isbn == "9780441172719"


def test_openlibrary_isbn_parses(monkeypatch):
    m = _provider(monkeypatch).lookup_by_isbn("978-0-441-17271-9")
    assert m.matched and m.title == "Dune" and m.author == "Frank Herbert"
    assert m.year == 1990 and m.page_count == 688 and m.isbn == "9780441172719"
    assert m.cover_url == "http://c/dune.jpg"


def test_openlibrary_no_match(monkeypatch):
    p = OpenLibraryProvider()
    monkeypatch.setattr(p.session, "get", lambda url, **k: FakeResp({"docs": []}))
    assert p.lookup("Nope").matched is False
    assert p.lookup("").matched is False


# -- ISBN barcode routing ------------------------------------------------
def test_is_isbn():
    assert barcode.is_isbn("9780441172719") is True
    assert barcode.is_isbn("9791234567896") is True      # 979 prefix
    assert barcode.is_isbn("012345678905") is False      # a UPC, not an ISBN
    assert barcode.is_isbn("978") is False


class _FakeBookProv:
    def lookup_by_isbn(self, isbn, year=None):
        from mediahound.metadata.base import BookMeta
        return BookMeta(True, source="openlibrary", title="Dune", author="Frank Herbert",
                        year=1965, format="Paperback", isbn=isbn, cover_url=None)


def test_barcode_isbn_autoroutes_to_book(monkeypatch):
    # even when the UI guessed "movie", a 978/979 code resolves as a book
    monkeypatch.setattr(meta_mod, "get_metadata_provider",
                        lambda cfg, mt=None: _FakeBookProv())
    out = barcode.lookup(None, "9780441172719", "movie")
    assert out["media_type"] == "book" and out["title"] == "Dune"
    assert out["author"] == "Frank Herbert" and out["meta"].isbn == "9780441172719"


# -- mock build + CSV + move ---------------------------------------------
def test_mock_build_has_books(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    coll = json.loads((site / "data" / "collection.json").read_text())
    books = [m for m in coll if m.get("media_type") == "book"]
    assert len(books) == 3
    dune = next(b for b in books if b["title"] == "Dune")
    assert dune["author"] == "Frank Herbert" and dune["page_count"] == 688
    assert dune["read"]["providers"]                       # where-to-read links present


def test_init_creates_books_folder(tmp_path):
    site = tmp_path / "s"
    cli.main(["init", str(site)])
    assert (site / "RawImages" / "books").is_dir()


def test_csv_imports_a_book(tmp_path):
    from mediahound.csvio import import_csv
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    csv_path = tmp_path / "b.csv"
    csv_path.write_text("media_type,title,author,year,format,publisher,pages\n"
                        "book,The Hobbit,J.R.R. Tolkien,1937,Hardcover,Allen & Unwin,310\n")
    import_csv(cfg, store, csv_path, online=False, log=lambda *_: None)
    hobbit = next(m for m in store.collection if m["title"] == "The Hobbit")
    assert hobbit["media_type"] == "book" and hobbit["author"] == "J.R.R. Tolkien"
    assert hobbit["publisher"] == "Allen & Unwin" and hobbit["page_count"] == 310
    assert hobbit["format"] == "Hardcover"


def test_move_to_book_clears_other_type_fields(tmp_path):
    from mediahound import pipeline
    cfg = load_config(tmp_path / "config.toml") if (tmp_path / "config.toml").is_file() else None
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    store.upsert_movie({"id": "x1", "media_type": "movie", "title": "Not A Movie",
                        "director": "D", "studio": "S", "actors": ["a"], "format": "DVD"})
    store.corrections = {"x1": {"media_type": "book", "author": "Real Author"}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    m = store.find_movie("x1")
    assert m["media_type"] == "book" and m["author"] == "Real Author"
    for gone in ("director", "studio", "actors"):
        assert gone not in m                               # movie-only fields cleared
    assert m["format"] == "Hardcover"                      # DVD normalised to a book format
