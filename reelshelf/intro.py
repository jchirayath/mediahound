"""Build the short enticing 'intro' hook — deliberately NOT a plot synopsis."""
from __future__ import annotations

from .identify.base import Identification
from .metadata.base import MovieMeta

_GENRE_HOOK = {
    "action": "Buckle up", "adventure": "An adventure awaits",
    "comedy": "Get ready to laugh", "drama": "A story that lingers",
    "horror": "Keep the lights on", "thriller": "Hold your breath",
    "science fiction": "Worlds beyond imagining", "sci-fi": "Worlds beyond imagining",
    "fantasy": "Step into another world", "romance": "Love, on its own terms",
    "crime": "Nothing is quite as it seems", "mystery": "A puzzle worth solving",
    "animation": "A feast for the eyes", "family": "Fun for everyone",
    "war": "Courage under fire", "western": "The frontier calls",
    "documentary": "Truth, stranger than fiction", "music": "Turn it up",
}


def make_intro(ident: Identification, meta: MovieMeta) -> str:
    """Priority: identifier-written hook (e.g. Claude) → tagline → templated hook."""
    if ident.intro and ident.intro.strip():
        return ident.intro.strip()
    if meta.tagline and meta.tagline.strip():
        return meta.tagline.strip()

    genres = [g.lower() for g in (meta.genres or [])]
    lead = next((_GENRE_HOOK[g] for g in genres if g in _GENRE_HOOK), None)
    if not lead:
        for g in genres:
            for key, hook in _GENRE_HOOK.items():
                if key in g:
                    lead = hook
                    break
            if lead:
                break

    bits = []
    if meta.year:
        era = f"{meta.year // 10 * 10}s"
        gtxt = (meta.genres[0].lower() if meta.genres else "classic")
        bits.append(f"a {era} {gtxt}")
    if lead:
        title = meta.title or ident.title or "this one"
        tail = f" — {bits[0]} worth revisiting." if bits else "."
        return f"{lead}{tail}"
    # last-ditch: trim the overview to one sentence (still a hook, not the full plot)
    if meta.overview:
        first = meta.overview.split(". ")[0].strip()
        return (first[:160] + "…") if len(first) > 160 else first + "."
    return "A title from the collection — give it a spin."
