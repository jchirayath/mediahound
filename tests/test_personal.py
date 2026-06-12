"""Feature 04 — personal catalog: ratings/notes/tags + loans stay private (never published)."""
import json
import threading
import time
import urllib.request

import pytest

from mediahound import cli
from mediahound.config import load_config
from mediahound.pipeline import PRIVATE_FIELDS, _public_item
from mediahound.publish import _site_files


@pytest.fixture
def built(tmp_path):
    site = tmp_path / "site"
    assert cli.main(["init", str(site)]) == 0
    assert cli.main(["build", "--config", str(site / "config.toml"), "--mock"]) == 0
    return site, load_config(site / "config.toml")


def test_public_item_strips_personal_fields():
    m = {"id": "x", "title": "T", "my_rating": 9, "my_note": "secret", "tags": ["a"], "loan": {"to": "Bob"}}
    pub = _public_item(m)
    assert pub == {"id": "x", "title": "T"}
    assert all(f not in pub for f in PRIVATE_FIELDS)


def test_personal_data_never_reaches_published_catalog(built):
    site, cfg = built
    movie = next(m for m in json.loads((cfg.data_dir / "collection.json").read_text())
                 if m.get("media_type", "movie") == "movie")
    (cfg.data_dir / "corrections.json").write_text(json.dumps(
        {movie["id"]: {"my_rating": 8, "my_note": "private thoughts", "tags": ["Christmas"]}}))
    (cfg.data_dir / "loans.json").write_text(json.dumps(
        {movie["id"]: {"to": "Alice", "since": "2026-01-01", "returned": False}}))
    assert cli.main(["build", "--config", str(site / "config.toml")]) == 0

    coll = (cfg.data_dir / "collection.json").read_text()
    bundle = (cfg.data_dir / "bundle.js").read_text()
    for needle in ("private thoughts", "my_rating", "my_note", '"tags"', "Alice"):
        assert needle not in coll, needle
        assert needle not in bundle, needle


def test_corrections_and_loans_excluded_from_publish(built):
    _, cfg = built
    (cfg.data_dir / "corrections.json").write_text("{}")
    (cfg.data_dir / "loans.json").write_text("{}")
    published = set(_site_files(cfg.output_dir))
    assert not any(p.endswith("corrections.json") for p in published)
    assert not any(p.endswith("loans.json") for p in published)
    # the public catalog + feeds still ship
    assert any(p.endswith("collection.json") for p in published)


# -- /api/loans persistence ----------------------------------------------
def _free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


def _post(url, obj, origin):
    import urllib.error
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Origin": origin})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_api_loans_persists(built):
    from mediahound import serve
    site, cfg = built
    port = _free_port()
    threading.Thread(target=serve.serve, daemon=True,
                     kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=True,
                                 open_browser=False, log=lambda *_: None)).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read(); break
        except OSError:
            time.sleep(0.05)
    status, body = _post(base + "/api/loans",
                         {"serenity-2005": {"to": "Bob", "since": "2026-06-01", "returned": False}},
                         origin=base)
    assert status == 200 and body["ok"] is True
    saved = json.loads((cfg.data_dir / "loans.json").read_text())
    assert saved["serenity-2005"]["to"] == "Bob"
