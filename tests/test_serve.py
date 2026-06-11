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


def _png_b64():
    import base64
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 50), (90, 60, 120)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_upload_saves_photo_into_rawimages(served_site):
    base, cfg = served_site
    status, body = _post(base + "/api/upload",
                         {"filename": "My Cover! .png", "media_type": "music", "data": _png_b64()},
                         origin=base)
    assert status == 200 and body["ok"] is True
    saved = cfg.input_dir / "audio" / body["saved"]
    assert saved.is_file()                              # landed in RawImages/audio/
    assert " " not in body["saved"] and "!" not in body["saved"]   # filename sanitised


def test_upload_rejects_non_image(served_site):
    import base64
    base, cfg = served_site
    status, body = _post(base + "/api/upload",
                         {"filename": "x.png", "media_type": "movie",
                          "data": base64.b64encode(b"not an image").decode()},
                         origin=base)
    assert status == 400 and body["ok"] is False
    assert not list((cfg.input_dir / "video").glob("*"))   # nothing written


def test_upload_cross_origin_refused(served_site):
    base, cfg = served_site
    status, body = _post(base + "/api/upload",
                         {"filename": "x.png", "media_type": "movie", "data": _png_b64()},
                         origin="http://evil.example")
    assert status == 403 and body["ok"] is False


def test_phone_mode_prints_qr_and_token_gates_writes(tmp_path):
    import re
    site = tmp_path / "site"
    assert cli.main(["init", str(site)]) == 0
    assert cli.main(["build", "--config", str(site / "config.toml"), "--mock"]) == 0
    cfg = load_config(site / "config.toml")
    port = _free_port()
    lines = []
    threading.Thread(
        target=serve.serve,
        kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=True,
                    open_browser=False, log=lines.append, phone=True),
        daemon=True,
    ).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read()
            break
        except OSError:
            time.sleep(0.05)
    txt = "\n".join(lines)
    assert "PHONE MODE" in txt                       # the banner printed
    m = re.search(r"\?t=([A-Za-z0-9_-]+)", txt)       # a token URL was printed (for the QR)
    assert m, "no token URL printed"
    token = m.group(1)

    def upload(tok):
        req = urllib.request.Request(
            base + "/api/upload",
            data=json.dumps({"filename": "a.png", "media_type": "movie", "data": _png_b64()}).encode(),
            method="POST", headers={"Content-Type": "application/json", "Origin": base})
        if tok:
            req.add_header("X-MediaHound-Token", tok)
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    assert upload(None) == 403          # no token → refused
    assert upload("nope") == 403        # wrong token → refused
    assert upload(token) == 200         # correct token → accepted


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
