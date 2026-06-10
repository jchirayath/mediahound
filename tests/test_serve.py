"""serve --admin: the localhost write API persists edits into data/ and refuses cross-origin."""
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from mediahound import cli, serve
from mediahound.config import load_config


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def served_site(tmp_path):
    """A built mock site served by `serve(admin=True)` on a background thread."""
    site = tmp_path / "site"
    assert cli.main(["init", str(site)]) == 0
    assert cli.main(["build", "--config", str(site / "config.toml"), "--mock"]) == 0
    cfg = load_config(site / "config.toml")
    port = _free_port()
    t = threading.Thread(
        target=serve.serve,
        kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=True,
                    open_browser=False, log=lambda *_: None),
        daemon=True,
    )
    t.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):                      # wait for the server to accept connections
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read()
            break
        except OSError:
            time.sleep(0.05)
    yield base, cfg


def _post(url, obj, origin=None):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_merge_helper_merges_per_id_fields():
    out = serve._merge({"a": {"title": "X", "requery": False}}, {"a": {"title": "Y"}})
    assert out["a"] == {"title": "Y", "requery": False}


def test_ping_reports_admin(served_site):
    base, _ = served_site
    body = json.loads(urllib.request.urlopen(base + "/api/ping", timeout=2).read())
    assert body["ok"] is True and body["admin"] is True


def test_same_origin_correction_persists_to_disk(served_site):
    base, cfg = served_site
    status, body = _post(base + "/api/corrections",
                         {"demo-id": {"title": "Edited Title"}}, origin=base)
    assert status == 200 and body["ok"] is True
    saved = json.loads((cfg.data_dir / "corrections.json").read_text())
    assert saved["demo-id"]["title"] == "Edited Title"


def test_cross_origin_write_is_refused(served_site):
    base, cfg = served_site
    status, body = _post(base + "/api/corrections",
                         {"evil": {"title": "nope"}}, origin="http://evil.example")
    assert status == 403 and body["ok"] is False
    saved = json.loads((cfg.data_dir / "corrections.json").read_text()) \
        if (cfg.data_dir / "corrections.json").is_file() else {}
    assert "evil" not in saved


def test_import_adds_titles_from_partial_csv(served_site):
    base, cfg = served_site
    csv = "media_type,title,artist\nmovie,The Goonies,\nmusic,Abbey Road,The Beatles\n"
    status, body = _post(base + "/api/import", {"csv": csv, "online": False}, origin=base)
    assert status == 200 and body["ok"] is True and body["added"] == 2
    titles = {i["title"]: i.get("media_type") for i in
              json.loads((cfg.data_dir / "collection.json").read_text())}
    assert titles.get("The Goonies") == "movie"
    assert titles.get("Abbey Road") == "music"


def test_import_title_only_csv(served_site):
    base, cfg = served_site
    status, body = _post(base + "/api/import", {"csv": "title\nSolo Title\n", "online": False}, origin=base)
    assert status == 200 and body["added"] == 1     # only a `title` column → still works


def test_serve_without_admin_has_no_write_api(tmp_path):
    site = tmp_path / "site"
    assert cli.main(["init", str(site)]) == 0
    assert cli.main(["build", "--config", str(site / "config.toml"), "--mock"]) == 0
    cfg = load_config(site / "config.toml")
    port = _free_port()
    threading.Thread(
        target=serve.serve,
        kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=False,
                    open_browser=False, log=lambda *_: None),
        daemon=True,
    ).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read()
            break
        except OSError:
            time.sleep(0.05)
    body = json.loads(urllib.request.urlopen(base + "/api/ping", timeout=2).read())
    assert body["admin"] is False
    status, body = _post(base + "/api/corrections", {"x": {"title": "y"}}, origin=base)
    assert status == 404            # write endpoints are not mounted without --admin
