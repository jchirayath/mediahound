"""Where-to-listen deep links (keyless).

Exact track/album links need a Spotify or Apple Music key; these are search-URL deep links
that open the right query in each service — the music analogue of the JustWatch fallback.
"""
from __future__ import annotations

import urllib.parse

LISTEN_BASE = {
    "Spotify": "https://open.spotify.com/search/",
    "Apple Music": "https://music.apple.com/us/search?term=",
    "YouTube Music": "https://music.youtube.com/search?q=",
}
DEFAULT_SERVICES = ("Spotify", "Apple Music", "YouTube Music")


def listen_links(artist: str | None, title: str | None, services=DEFAULT_SERVICES) -> dict:
    """Return {checked, providers:[{name, url}]} of where-to-listen search links."""
    q = urllib.parse.quote(f"{(artist or '').strip()} {(title or '').strip()}".strip())
    return {"checked": True,
            "providers": [{"name": s, "url": LISTEN_BASE[s] + q}
                          for s in services if s in LISTEN_BASE]}


READ_BASE = {
    "Open Library": "https://openlibrary.org/search?q=",
    "Goodreads": "https://www.goodreads.com/search?q=",
    "Google Books": "https://www.google.com/search?tbm=bks&q=",
}
READ_SERVICES = ("Open Library", "Goodreads", "Google Books")


def read_links(author: str | None, title: str | None, services=READ_SERVICES) -> dict:
    """Return {checked, providers:[{name, url}]} of where-to-read/find-the-book search links."""
    q = urllib.parse.quote(f"{(title or '').strip()} {(author or '').strip()}".strip())
    return {"checked": True,
            "providers": [{"name": s, "url": READ_BASE[s] + q}
                          for s in services if s in READ_BASE]}
