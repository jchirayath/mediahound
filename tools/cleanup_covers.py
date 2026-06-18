#!/usr/bin/env python3
"""Claude title-cleanup pass for albums still missing covers after fetch_covers.py.

Many residual misses fail only on messy *text*, not on being genuinely coverless:
  • HTML-entity artifacts — "&Amp;" should be "&" (broke "Crosby, Stills &Amp; Nash" etc.)
  • noise suffixes — "(Bonus Disc)", "(Disc 1)", "(Expanded Edition)", "(Ost)", ", The"
  • artist aliases / junk — "T.A.F.K.A.P" → Prince; "Soundtrack - Shrek" → Various
This normalizes the query (plus a small curated correction map for releases I can identify by
name), SKIPS obvious live bootlegs / personal comps (date-venue titles — no commercial cover
exists), and re-runs the same validated providers (iTunes/Deezer/Discogs) from fetch_covers.

Usage:  cleanup_covers.py /path/to/Library/config.toml
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
import fetch_covers                                   # reuse best_cover() + the validated providers
from mediahound.config import load_config
from mediahound.store import Store
from mediahound import pipeline

# Live bootlegs / radio / personal comps: a date-venue or known-bootleg title → no commercial cover.
_COVERLESS = re.compile(
    r"\b(19|20)\d\d[-/. ]\d\d?[-/. ]\d\d?\b|\b\d{4}-\d{2}-\d{2}\b|"
    r"live (from|at|rock am ring|\d)|fleet center|wembley|winterland|showbox|"
    r"the gorge \(|on the road:|kfog|ultra rare trax|tesco store|"
    r"download festival|eurotour|from the horde|crazy horse \)|d&t \d|bonaroo|"
    r"healing sounds of nature|stotrams|venkys|club 2k|essential mix \d|"
    r"blank generation|driven to the edge", re.I)

# Releases I can identify by name but whose stored text won't match any provider as-is.
_CORRECT = {
    ("emancipation", "t.a.f.k.a.p"): ("Emancipation", "Prince"),
    ("gold experience, the", "t.a.f.k.a.p"): ("The Gold Experience", "Prince"),
    ("symbol album", "prince & the new power generation"): ("Love Symbol Album", "Prince"),
    ('sign "â®" the times 2009', "prince"): ("Sign o' the Times", "Prince"),
    ("invest", "papa roach"): ("Infest", "Papa Roach"),
    ("only trust your heart", "diana krall dave grusin"): ("Only Trust Your Heart", "Diana Krall"),
    ("george martin: in my life", "various artists"): ("In My Life", "George Martin"),
    ("girl 6 (ost)", "prince"): ("Girl 6", "Prince"),
    ("tails (feat. nine stories)", "lisa loeb"): ("Tails", "Lisa Loeb"),
    ("two rooms (celebrating the son)", "eric clapton"): ("Two Rooms: Celebrating the Songs of Elton John & Bernie Taupin", ""),
    ("pure ella the very best of ell", "ella fitzgerald"): ("Pure Ella", "Ella Fitzgerald"),
}

_NOISE = re.compile(
    r"\s*\((?:"
    r"disc\s*\w[^)]*|cd\s*\d[^)]*|\d+\s*of\s*\d+|#\d+|"
    r"bonus[^)]*|expanded[^)]*|limited[^)]*|special edition[^)]*|deluxe[^)]*|"
    r"ost|original soundtrack|original [^)]*cast|picture cd[^)]*|"
    r"spanish version|\d{4} version|remaster[^)]*|"
    r"plus ltd[^)]*|with crazy horse|celebrating[^)]*"
    r")\)\s*", re.I)
_JUNK_ARTIST = re.compile(r"^(various|soundtrack|original soundtrack)\b|soundtrack\s*-", re.I)


def _decanon(s: str) -> str:
    return html.unescape((s or "").replace("&Amp;", "&").replace("&amp;", "&")).strip()


def cleaned_query(title: str, artist: str):
    """Return (title, artist) to look up, or (None, None) if it's not worth trying."""
    raw_t, raw_a = title, artist
    key = (raw_t.strip().lower(), (raw_a or "").strip().lower())
    if key in _CORRECT:
        return _CORRECT[key]
    blob = f"{raw_t} {raw_a}"
    if _COVERLESS.search(blob):
        return None, None
    t, a = _decanon(raw_t), _decanon(raw_a)
    # strip parenthetical noise, then move a trailing ", The" to the front
    prev = None
    while prev != t:
        prev = t
        t = _NOISE.sub(" ", t).strip(" -")
    t = re.sub(r"\s+", " ", t).strip()
    m = re.match(r"^(.*?),\s*the$", t, re.I)
    if m:
        t = "The " + m.group(1).strip()
    t = re.sub(r"\s*/\s*\w[\w ]*$", "", t)             # "Full Collapse / Waiting" -> "Full Collapse"
    # artist aliases / junk
    if re.search(r"\bt\.?a\.?f\.?k\.?a\.?p\b|prince & the npg|prince & the new power", a, re.I):
        a = "Prince"
    if _JUNK_ARTIST.search(a):
        a = ""                                         # let it search as a Various-Artists/soundtrack title
    return t.strip(), a.strip()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cfg = load_config(Path(sys.argv[1]).resolve())
    store = Store(cfg.data_dir)
    todo = [m for m in store.collection if m.get("media_type") == "music" and not m.get("poster")]
    print(f"Cleanup pass over {len(todo)} still-uncovered album(s)…", flush=True)

    fixed = skipped = tried = 0
    for i, m in enumerate(todo, 1):
        t, a = cleaned_query(m.get("title", ""), m.get("artist", ""))
        if not t:
            skipped += 1
            continue
        tried += 1
        try:
            r = fetch_covers.best_cover(t, a)
        except Exception:
            r = None
        if r and r.get("cover"):
            m["poster"], m["images"] = r["cover"], [r["cover"]]
            m["source"] = {"name": r["source"] + " (cleaned)", "url": r.get("url", "")}
            fixed += 1
            print(f"  ✓ {m.get('title','')[:34]!r} → {t!r}/{a!r} [{r['source']}]", flush=True)
        if i % 25 == 0:
            store.save()
    store.save()
    pipeline._write_site(cfg, store)
    print(f"\nDone. {fixed} newly covered (tried {tried}, skipped {skipped} as coverless bootleg/comp).",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
