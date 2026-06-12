"""UI library switcher — recents store + live switch-library / create-library endpoints."""
import json
import threading
import time
import urllib.error
import urllib.request

from mediahound import cli, libraries, serve
from mediahound.config import load_config

# Recents isolation comes from the autouse `_isolated_app_config` fixture in conftest.py.


def _make_library(tmp_path, name, title):
    site = tmp_path / name
    cli.main(["init", str(site)])
    cfg_file = site / "config.toml"
    cfg_file.write_text(cfg_file.read_text().replace('title    = "My Media Collection"',
                                                     f'title    = "{title}"'))
    cli.main(["build", "--config", str(cfg_file), "--mock"])
    return site


# -- recents store --------------------------------------------------------
def test_recents_upsert_and_prune(tmp_path):
    a = _make_library(tmp_path, "a", "Library A")
    assert libraries.list_recent() == []
    libraries.add_recent(a, "Library A")
    rec = libraries.list_recent()
    assert len(rec) == 1 and rec[0]["title"] == "Library A" and rec[0]["path"] == str(a.resolve())
    libraries.add_recent(a, "Library A")                     # idempotent upsert
    assert len(libraries.list_recent()) == 1
    # a recorded library whose folder no longer qualifies is pruned on read
    (a / "config.toml").unlink()
    assert libraries.list_recent() == []


def test_remove_recent(tmp_path):
    a = _make_library(tmp_path, "a", "A")
    libraries.add_recent(a, "A")
    libraries.remove_recent(a)
    assert libraries.list_recent() == []


# -- live switch over the admin server -----------------------------------
def _free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


def _serve(cfg, port, token=None):
    threading.Thread(target=serve.serve, daemon=True,
                     kwargs=dict(cfg=cfg, host="127.0.0.1", port=port, admin=True,
                                 open_browser=False, log=lambda *_: None,
                                 phone=bool(token))).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read(); return base
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("server didn't start")


def _post(url, obj, origin, token=None):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Origin": origin})
    if token:
        req.add_header("X-MediaHound-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_switch_library_live(tmp_path):
    a = _make_library(tmp_path, "a", "Library A")
    b = _make_library(tmp_path, "b", "Library B")
    cfg_a = load_config(a / "config.toml")
    base = _serve(cfg_a, _free_port())

    # serving A: its title shows
    assert json.loads(urllib.request.urlopen(base + "/data/site.json").read())["title"] == "Library A"
    # /api/libraries lists A as current (it was recorded on serve start)
    libs = json.loads(urllib.request.urlopen(base + "/api/libraries").read())
    assert libs["ok"] and libs["current"]["title"] == "Library A"

    # switch to B → subsequent requests serve B
    status, body = _post(base + "/api/switch-library", {"path": str(b)}, origin=base)
    assert status == 200 and body["ok"] and body["title"] == "Library B"
    assert json.loads(urllib.request.urlopen(base + "/data/site.json").read())["title"] == "Library B"
    assert str(b.resolve()) in {r["path"] for r in libraries.list_recent()}


def test_switch_rejects_non_library(tmp_path):
    a = _make_library(tmp_path, "a", "A")
    base = _serve(load_config(a / "config.toml"), _free_port())
    status, body = _post(base + "/api/switch-library", {"path": str(tmp_path / "nope")}, origin=base)
    assert status == 400 and body["ok"] is False


def test_create_library_live(tmp_path):
    a = _make_library(tmp_path, "a", "A")
    base = _serve(load_config(a / "config.toml"), _free_port())
    newdir = tmp_path / "fresh"
    status, body = _post(base + "/api/create-library", {"path": str(newdir)}, origin=base)
    assert status == 200 and body["ok"] is True
    assert (newdir / "config.toml").is_file() and (newdir / "data" / "collection.json").is_file()
    assert json.loads(urllib.request.urlopen(base + "/data/site.json").read())  # now serving the new one


def test_switch_refused_over_phone_lan(tmp_path):
    import re
    a = _make_library(tmp_path, "a", "A")
    b = _make_library(tmp_path, "b", "B")
    port = _free_port()
    lines = []
    threading.Thread(target=serve.serve, daemon=True,
                     kwargs=dict(cfg=load_config(a / "config.toml"), host="127.0.0.1", port=port,
                                 admin=True, open_browser=False, log=lines.append, phone=True)).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1).read(); break
        except OSError:
            time.sleep(0.05)
    token = re.search(r"\?t=([A-Za-z0-9_-]+)", "\n".join(lines)).group(1)
    status, body = _post(base + "/api/switch-library", {"path": str(b)}, origin=base, token=token)
    assert status == 403 and body["ok"] is False           # even with the token, not over the LAN
