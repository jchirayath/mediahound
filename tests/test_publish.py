"""Publish: only the generated site is uploaded, and the Netlify deploy is orchestrated
correctly (create site → digest → upload required → wait ready). The API is faked."""
import hashlib
import json

from mediahound import cli, publish
from mediahound.config import load_config


def _built_site(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    # add a stray source photo + secret that must NOT be published
    (site / "RawImages" / "video").mkdir(parents=True, exist_ok=True)
    (site / "RawImages" / "video" / "cover.jpg").write_bytes(b"\xff\xd8\xff")
    (site / ".env").write_text("TMDB_API_KEY=secret")
    return load_config(site / "config.toml")


def test_site_files_excludes_sources_and_secrets(tmp_path):
    cfg = _built_site(tmp_path)
    files = publish._site_files(cfg.output_dir.resolve())
    paths = set(files)
    assert "/index.html" in paths
    assert any(p.startswith("/data/") for p in paths)          # generated catalog is included
    assert not any(p.startswith("/RawImages") for p in paths)  # source photos excluded
    assert "/.env" not in paths and "/config.toml" not in paths
    assert not any("/." in p for p in paths)                   # no dotfiles/dotdirs


class _FakeResp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def test_deploy_creates_site_uploads_and_returns_url(tmp_path, monkeypatch):
    cfg = _built_site(tmp_path)
    index_sha = hashlib.sha1((cfg.output_dir / "index.html").read_bytes()).hexdigest()  # noqa: S324
    calls = {"put": 0}

    class _FakeRequests:
        def post(self, url, **kw):
            if url.endswith("/sites"):
                return _FakeResp({"id": "site1", "name": "lucky-otter"})
            if url.endswith("/deploys"):
                # Netlify says it still needs just the index.html digest
                return _FakeResp({"id": "dep1", "required": [index_sha]})
            raise AssertionError(url)

        def put(self, url, **kw):
            calls["put"] += 1
            return _FakeResp({})

        def get(self, url, **kw):
            return _FakeResp({"state": "ready", "ssl_url": "https://lucky-otter.netlify.app"})

    monkeypatch.setattr(publish, "requests", _FakeRequests())
    url = publish.deploy(cfg, "tok-123", log=lambda *_: None)
    assert url == "https://lucky-otter.netlify.app"
    assert calls["put"] == 1                                    # uploaded exactly the required file
    saved = json.loads((cfg.data_dir / ".netlify-site.json").read_text())
    assert saved["site_id"] == "site1"                         # site id remembered for next time
