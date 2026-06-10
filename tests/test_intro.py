"""Intro hook priority: identifier hook → tagline → genre template → overview → default."""
from reelshelf.identify.base import Identification
from reelshelf.intro import make_intro
from reelshelf.metadata.base import MovieMeta

_ID = Identification(True, "Film", 1999, "DVD")


def test_identifier_hook_wins():
    meta = MovieMeta(True, tagline="A tagline", genres=["Drama"], year=1999)
    ident = Identification(True, "Film", 1999, "DVD", intro="  Claude's hook.  ")
    assert make_intro(ident, meta) == "Claude's hook."


def test_tagline_used_when_no_identifier_hook():
    meta = MovieMeta(True, tagline="One ring to rule them all.", genres=["Fantasy"], year=2001)
    assert make_intro(_ID, meta) == "One ring to rule them all."


def test_genre_template_when_no_tagline():
    meta = MovieMeta(True, genres=["Horror"], year=1981, title="Spookies")
    out = make_intro(_ID, meta)
    assert out.startswith("Keep the lights on")
    assert "1980s" in out                                  # era from year


def test_substring_genre_match():
    meta = MovieMeta(True, genres=["Epic Science Fiction"], year=1977)
    assert make_intro(_ID, meta).startswith("Worlds beyond imagining")


def test_overview_fallback_when_no_genre_hook():
    meta = MovieMeta(True, genres=["Unknownia"], overview="First sentence here. Second one.")
    out = make_intro(_ID, meta)
    assert out.startswith("First sentence here")
    assert "Second one" not in out                         # only the first sentence (a hook)


def test_last_ditch_default():
    assert make_intro(_ID, MovieMeta(True)) == "A title from the collection — give it a spin."
