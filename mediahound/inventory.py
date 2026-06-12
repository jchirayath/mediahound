"""Printable inventory — a clean, self-contained HTML document of the whole catalog.

Grouped by media type, with per-type and grand-total estimated values, ready to **print or
Save-as-PDF** (insurance records, offline sharing). Zero dependencies and no network: the page is
fully inline (its own CSS), and the browser's print dialog produces the PDF. Personal fields
(ratings/notes/tags) are never included — this is a clean catalog listing.
"""
from __future__ import annotations

import html
from datetime import UTC, datetime

_TYPE_ORDER = ["movie", "music", "book", "game", "audiobook"]
_TYPE_LABEL = {"movie": "Movies", "music": "Music", "book": "Books",
               "game": "Video games", "audiobook": "Audiobooks"}
# the "creator" column header + field per media type
_CREATOR = {
    "movie": ("Director", lambda m: m.get("director")),
    "music": ("Artist", lambda m: m.get("artist")),
    "book": ("Author", lambda m: m.get("author")),
    "game": ("Developer", lambda m: m.get("developer")),
    "audiobook": ("Author / narrator", lambda m: " / ".join(
        x for x in (m.get("author"), m.get("narrator")) if x)),
}


def _value(m: dict) -> float:
    r = m.get("resale") or {}
    v = r.get("mid")
    return float(v) if isinstance(v, (int, float)) else 0.0


def _currency(collection) -> str:
    for m in collection:
        cur = (m.get("resale") or {}).get("currency")
        if cur and cur != "local":
            return "$" if cur == "USD" else f"{cur} "
    return "$"


def render_inventory(collection: list, site: dict | None = None, *,
                     generated_at: str | None = None) -> str:
    """Return a complete, self-contained printable HTML document for the catalog."""
    site = site or {}
    esc = html.escape
    title = esc(str(site.get("title") or "My Media Collection"))
    when = esc(generated_at or datetime.now(UTC).strftime("%Y-%m-%d"))
    sym = _currency(collection)

    groups: dict[str, list] = {}
    for m in collection:
        groups.setdefault(m.get("media_type") or "movie", []).append(m)

    total_items = len(collection)
    total_value = sum(_value(m) for m in collection)
    present = [t for t in _TYPE_ORDER if groups.get(t)]
    present += [t for t in groups if t not in _TYPE_ORDER]   # any unknown types, last
    counts = " · ".join(f"{len(groups[t])} {_TYPE_LABEL.get(t, t).lower()}" for t in present)

    def money(v: float) -> str:
        return f"{sym}{int(round(v)):,}"

    sections = []
    for t in present:
        items = sorted(groups[t], key=lambda m: (str(m.get("title") or "").lower(),
                                                 m.get("year") or 0))
        chead, cfield = _CREATOR.get(t, ("Creator", lambda m: m.get("director")))
        subtotal = sum(_value(m) for m in items)
        rows = []
        for i, m in enumerate(items, 1):
            rows.append(
                "<tr>"
                f"<td class=num>{i}</td>"
                f"<td class=ttl>{esc(str(m.get('title') or 'Untitled'))}</td>"
                f"<td>{esc(str(cfield(m) or ''))}</td>"
                f"<td class=num>{esc(str(m.get('year') or ''))}</td>"
                f"<td>{esc(str(m.get('format') or ''))}</td>"
                f"<td class=num>{esc(str(m.get('rating') or ''))}</td>"
                f"<td class=num>{money(_value(m)) if _value(m) else ''}</td>"
                "</tr>")
        sections.append(
            f'<section class="grp">'
            f'<h2>{_TYPE_LABEL.get(t, esc(t.title()))} '
            f'<span class="grp-meta">{len(items)} item(s) · est. {money(subtotal)}</span></h2>'
            '<table><thead><tr>'
            '<th class=num>#</th><th>Title</th>'
            f'<th>{esc(chead)}</th><th class=num>Year</th><th>Format</th>'
            '<th class=num>Rating</th><th class=num>Est. value</th>'
            '</tr></thead><tbody>'
            + "".join(rows) +
            '</tbody></table></section>')

    return _PAGE.format(
        title=title, when=when, total_items=total_items,
        total_value=money(total_value), counts=counts or "empty catalog",
        sections="\n".join(sections) or "<p>No items in this catalog yet.</p>")


_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{title} — Inventory</title>
<style>
  :root {{ --ink:#16232a; --muted:#5b6b73; --line:#d7dde0; --accent:#e97b0c; }}
  * {{ box-sizing:border-box; }}
  body {{ font:14px/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    color:var(--ink); margin:0; padding:28px 32px; background:#fff; }}
  .bar {{ display:flex; justify-content:space-between; align-items:center; gap:16px;
    margin-bottom:18px; }}
  .bar button {{ font:600 13px/1 inherit; padding:9px 16px; border-radius:8px; cursor:pointer;
    border:1px solid var(--accent); background:var(--accent); color:#fff; }}
  h1 {{ font-size:22px; margin:0 0 2px; }}
  .sub {{ color:var(--muted); font-size:12.5px; }}
  .totals {{ margin:10px 0 20px; padding:12px 16px; border:1px solid var(--line);
    border-radius:10px; background:#fafbfb; }}
  .totals .big {{ font-size:18px; font-weight:700; }}
  .grp {{ margin:0 0 22px; break-inside:avoid; }}
  h2 {{ font-size:15px; margin:0 0 8px; padding-bottom:5px; border-bottom:2px solid var(--ink);
    display:flex; justify-content:space-between; align-items:baseline; }}
  .grp-meta {{ font-size:12px; font-weight:500; color:var(--muted); }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
  th, td {{ text-align:left; padding:5px 8px; border-bottom:1px solid var(--line);
    vertical-align:top; }}
  th {{ font-size:11px; text-transform:uppercase; letter-spacing:.03em; color:var(--muted);
    border-bottom:1px solid var(--ink); }}
  td.num, th.num {{ text-align:right; white-space:nowrap; }}
  td.ttl {{ font-weight:600; }}
  tr {{ break-inside:avoid; }}
  .foot {{ margin-top:22px; color:var(--muted); font-size:11px;
    border-top:1px solid var(--line); padding-top:10px; }}
  @media print {{
    body {{ padding:0; }}
    .no-print {{ display:none !important; }}
    thead {{ display:table-header-group; }}   /* repeat the column headers on every page */
    @page {{ margin:14mm; }}
  }}
</style></head>
<body>
  <div class="bar">
    <div>
      <h1>{title}</h1>
      <div class="sub">Collection inventory · generated {when}</div>
    </div>
    <button class="no-print" onclick="window.print()">🖨 Print / Save as PDF</button>
  </div>
  <div class="totals">
    <div class="big">{total_items} item(s) · estimated value {total_value}</div>
    <div class="sub">{counts}</div>
  </div>
  {sections}
  <div class="foot">Estimated values are heuristic resale guesses (see each item's sold-listing
    link in the app), provided for reference only. Generated by MediaHound.</div>
</body></html>"""
