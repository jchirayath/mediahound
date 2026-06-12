"""Printable inventory — the HTML generator + the `export --format inventory` CLI path."""
from mediahound import cli
from mediahound.config import load_config
from mediahound.inventory import render_inventory
from mediahound.store import Store

_ITEMS = [
    {"media_type": "movie", "title": "Heat", "year": 1995, "format": "Blu-ray", "director": "Michael Mann",
     "rating": 8.3, "resale": {"mid": 9, "currency": "USD"}},
    {"media_type": "music", "title": "Rumours", "year": 1977, "format": "Vinyl", "artist": "Fleetwood Mac",
     "resale": {"mid": 25, "currency": "USD"}},
    {"media_type": "audiobook", "title": "Becoming", "year": 2018, "format": "CD", "author": "Michelle Obama",
     "narrator": "Michelle Obama", "resale": {"mid": 6, "currency": "USD"}},
]


def test_render_groups_and_totals():
    html = render_inventory(_ITEMS, {"title": "My Vault"}, generated_at="2026-06-12")
    assert "<title>My Vault — Inventory</title>" in html
    assert "3 item(s) · estimated value $40" in html          # 9 + 25 + 6
    # one section per present type, with the right creator column header
    assert "<h2>Movies " in html and "<h2>Music " in html and "<h2>Audiobooks" in html
    assert "Director" in html and "Artist" in html and "Author / narrator" in html
    assert "Michelle Obama / Michelle Obama" in html          # audiobook author / narrator
    assert "$25" in html                                       # per-item value rendered
    assert "@media print" in html and "window.print()" in html


def test_render_escapes_html():
    html = render_inventory([{"media_type": "movie", "title": "<script>x</script>",
                              "director": "A & B", "resale": {}}])
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html and "A &amp; B" in html


def test_render_empty_catalog():
    html = render_inventory([])
    assert "0 item(s)" in html and "No items in this catalog yet." in html


def test_value_only_counts_numeric_mid():
    html = render_inventory([{"media_type": "movie", "title": "X", "resale": {"mid": None}}])
    assert "1 item(s) · estimated value $0" in html


def test_cli_export_inventory_writes_html(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    out = tmp_path / "inv.html"
    cli.main(["export", "--config", str(site / "config.toml"), "--format", "inventory", "-o", str(out)])
    html = out.read_text()
    assert html.startswith("<!DOCTYPE html>")
    cfg = load_config(site / "config.toml")
    n = len(Store(cfg.data_dir).collection)
    # every demo type appears as a section
    for label in ("Movies", "Music", "Books", "Video games", "Audiobooks"):
        assert f">{label} " in html or f">{label}<" in html or f"{label} <span" in html
    assert f"{n} item(s)" in html
