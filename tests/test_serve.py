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


def test_api_keys_status_and_set(served_site, mem_keyring):
    base, cfg = served_site
    body = json.loads(urllib.request.urlopen(base + "/api/keys", timeout=2).read())
    assert body["keys"] == {"TMDB_API_KEY": False, "OMDB_API_KEY": False,
                            "ANTHROPIC_API_KEY": False, "DISCOGS_TOKEN": False}
    status, body = _post(base + "/api/keys", {"TMDB_API_KEY": "secret-123"}, origin=base)
    assert status == 200 and body["ok"] is True and body["changed"] == ["TMDB_API_KEY"]
    assert body["keys"]["TMDB_API_KEY"] is True
    assert "secret-123" not in json.dumps(body)          # the value is never echoed back
    from mediahound import keystore
    assert keystore.get_key("TMDB_API_KEY") == "secret-123"   # stored in the (mock) keychain


def test_api_keys_refused_over_phone_lan(tmp_path, mem_keyring):
    import re
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")
    port = _free_port()
    lines = []
    threading.Thread(target=serve.serve,
                     kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=True,
                                 open_browser=False, log=lines.append, phone=True),
                     daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read()
            break
        except OSError:
            time.sleep(0.05)
    token = re.search(r"\?t=([A-Za-z0-9_-]+)", "\n".join(lines)).group(1)
    req = urllib.request.Request(  # even WITH the valid token, keys can't be set over the LAN
        base + "/api/keys", data=json.dumps({"TMDB_API_KEY": "x"}).encode(), method="POST",
        headers={"Content-Type": "application/json", "Origin": base, "X-MediaHound-Token": token})
    try:
        urllib.request.urlopen(req, timeout=3)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 403


def test_publish_needs_token_when_none_set(served_site, mem_keyring):
    base, cfg = served_site
    status, body = _post(base + "/api/publish", {}, origin=base)
    assert status == 200 and body["ok"] is False and body["need_token"] is True


def test_publish_with_token_deploys(served_site, mem_keyring, monkeypatch):
    from mediahound import publish
    monkeypatch.setattr(publish, "deploy", lambda cfg, token, log=None: "https://demo.netlify.app")
    base, cfg = served_site
    status, body = _post(base + "/api/publish", {"token": "tok-xyz"}, origin=base)
    assert status == 200 and body["ok"] is True and body["url"] == "https://demo.netlify.app"
    from mediahound import keystore
    assert keystore.get_key("NETLIFY_AUTH_TOKEN") == "tok-xyz"   # token saved to keychain


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


def test_phone_mode_uses_fixed_token_from_env(tmp_path, monkeypatch):
    import re
    monkeypatch.setenv("MEDIAHOUND_TOKEN", "fixed-secret-abc123")
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
    m = re.search(r"\?t=([A-Za-z0-9_-]+)", txt)
    assert m and m.group(1) == "fixed-secret-abc123"   # the env token, not a random one

    # and that fixed token actually gates writes
    req = urllib.request.Request(
        base + "/api/upload",
        data=json.dumps({"filename": "a.png", "media_type": "movie", "data": _png_b64()}).encode(),
        method="POST", headers={"Content-Type": "application/json", "Origin": base,
                                "X-MediaHound-Token": "fixed-secret-abc123"})
    with urllib.request.urlopen(req, timeout=3) as r:
        assert r.status == 200


def test_rebuild_passes_online_flag(served_site, monkeypatch):
    # The photo-upload flow asks for an ONLINE rebuild so a barcode in the just-added photo gets
    # decoded + resolved; a bare rebuild stays offline. Verify the flag is threaded through to build().
    base, _cfg = served_site
    from mediahound import pipeline
    calls = []
    monkeypatch.setattr(pipeline, "build", lambda cfg, online=False, log=None: calls.append(online))
    s, r = _post(base + "/api/rebuild", {"online": True}, origin=base)
    assert s == 200 and r.get("ok") and r.get("online") is True
    s, r = _post(base + "/api/rebuild", {}, origin=base)
    assert s == 200 and r.get("online") is False
    assert calls == [True, False]


def test_try_barcode_resolves_decoded_code(tmp_path, monkeypatch):
    # "Snap the barcode" path: a code decoded from the photo is resolved via barcode.lookup.
    from mediahound import barcode, pipeline
    from mediahound.config import load_config
    site = tmp_path / "site"
    assert cli.main(["init", str(site)]) == 0
    cfg = load_config(site / "config.toml")
    seen = {}
    monkeypatch.setattr(barcode, "decode_image", lambda p: ["0602557876543"])

    def fake_lookup(c, upc, mt):
        seen.update(upc=upc, mt=mt)
        return {"media_type": "music", "upc": upc, "title": "Test Album",
                "artist": "X", "year": 2020, "meta": None}
    monkeypatch.setattr(barcode, "lookup", fake_lookup)

    out = pipeline._try_barcode(cfg, site / "RawImages" / "audio" / "x.jpg", "music")
    assert out and out["title"] == "Test Album"
    assert seen == {"upc": "0602557876543", "mt": "music"}


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
