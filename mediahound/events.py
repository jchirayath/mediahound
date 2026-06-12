"""Compact, append-only event log of every data change — add / remove / change.

The user asked for a *common* log of all adds, removes and changes, "as compact and space saving as
possible." So this is NDJSON (one event per line, append-only — never rewrites the catalog) tuned hard
for size:

  * timestamp is an integer **unix-second** (not a 25-char ISO string),
  * the op is a **single character**,
  * a change records only the **names** of the fields that changed — not their values. That is both the
    smallest possible record and privacy-safe: personal notes/ratings are never copied into a 2nd file.

  {"t":1718150400,"o":"+","id":"dune-1965"}                     add
  {"t":1718150400,"o":"-","id":"dune-1965"}                     remove
  {"t":1718150400,"o":"~","id":"dune-1965","f":["title","year"]} change (changed field names)
  {"t":1718150400,"o":"s","id":"dune-1965","v":1}               seen=1 / unseen=0
  {"t":1718150400,"o":"l","id":"dune-1965","v":"out","w":"Alex"} loan out / "back"
  {"t":1718150400,"o":"i","n":42,"src":"csv"}                    bulk import (n items)

It is admin/audit data: written under data/, **excluded from publish** (see publish.py), and the file
self-trims to the most recent MAX_EVENTS so it can't grow without bound.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

# op name -> single-char code stored on disk (compactness)
_OPS = {"add": "+", "remove": "-", "change": "~", "seen": "s", "loan": "l", "import": "i"}
MAX_EVENTS = 5000               # keep at most this many most-recent events
_TRIM_BYTES = 512 * 1024        # only pay for a trim once the file grows past ~½ MB


class EventLog:
    """Append-only NDJSON change log. `enabled=False` makes every add() a no-op (used to silence a
    forced full rebuild, which would otherwise re-log every item as an add)."""

    def __init__(self, data_dir, enabled: bool = True):
        self.path = Path(data_dir) / "events.jsonl"
        self.enabled = enabled

    def add(self, op: str, id: str | None = None, *, fields=None, value=None,
            who=None, n=None, src=None, ts: int | None = None) -> None:
        if not self.enabled:
            return
        ev = {"t": int(ts if ts is not None else time.time()), "o": _OPS.get(op, op)}
        if id:
            ev["id"] = id
        if fields:
            ev["f"] = sorted(set(fields))
        if value is not None:
            ev["v"] = value
        if who:
            ev["w"] = who
        if n is not None:
            ev["n"] = n
        if src:
            ev["src"] = src
        line = json.dumps(ev, ensure_ascii=False, separators=(",", ":"))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            return
        self._maybe_trim()

    def _maybe_trim(self) -> None:
        try:
            if self.path.stat().st_size < _TRIM_BYTES:
                return
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if len(lines) <= MAX_EVENTS:
                return
            self.path.write_text("\n".join(lines[-MAX_EVENTS:]) + "\n", encoding="utf-8")
        except OSError:
            return

    def recent(self, n: int = 200) -> list[dict]:
        """The most-recent n events, newest last, as parsed dicts."""
        if not self.path.is_file():
            return []
        out = []
        for ln in self.path.read_text(encoding="utf-8").splitlines()[-n:]:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out


class _NullEventLog(EventLog):
    """A log that records nothing (no data dir needed)."""

    def __init__(self):
        self.enabled = False
        self.path = Path("/dev/null")

    def add(self, *a, **k):
        return
