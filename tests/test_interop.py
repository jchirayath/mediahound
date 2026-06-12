"""Feature 03 — backup/restore, exporters (Letterboxd/JSON), and syndication feeds."""
import json
import zipfile

import pytest

from mediahound import cli
from mediahound.backup import make_backup, restore_backup
from mediahound.config import load_config
from mediahound.exporters import export_json, export_letterboxd
from mediahound.store import Store


@pytest.fixture
def mock_site(tmp_path):
    site = tmp_path / "site"
    assert cli.main(["init", str(site)]) == 0
    assert cli.main(["build", "--config", str(site / "config.toml"), "--mock"]) == 0
    return site, load_config(site / "config.toml")


# -- backup / restore -----------------------------------------------------
def test_backup_roundtrip_reproduces_data_and_omits_env(mock_site, tmp_path):
    site, cfg = mock_site
    (site / ".env").write_text("SECRET=keepme\n")               # a secret beside config.toml
    (cfg.input_dir / "audio").mkdir(parents=True, exist_ok=True)
    (cfg.input_dir / "audio" / "cover.jpg").write_bytes(b"not-really-a-jpeg")

    zpath = tmp_path / "lib.zip"
    n = make_backup(cfg, zpath)
    assert n > 0
    names = zipfile.ZipFile(zpath).namelist()
    assert "config.toml" in names
    assert any(x.startswith("data/") for x in names)
    assert any(x.startswith("RawImages/") for x in names)
    assert not any(".env" in x for x in names)                  # secret never archived

    dest = tmp_path / "restored"
    restore_backup(zpath, dest)
    # data/ round-trips byte-for-byte
    orig = (cfg.data_dir / "collection.json").read_bytes()
    assert (dest / "data" / "collection.json").read_bytes() == orig
    assert (dest / "RawImages" / "audio" / "cover.jpg").is_file()
    assert not (dest / ".env").exists()


def test_backup_no_photos_skips_rawimages(mock_site, tmp_path):
    site, cfg = mock_site
    (cfg.input_dir / "audio").mkdir(parents=True, exist_ok=True)
    (cfg.input_dir / "audio" / "x.jpg").write_bytes(b"x")
    zpath = tmp_path / "data.zip"
    make_backup(cfg, zpath, no_photos=True)
    names = zipfile.ZipFile(zpath).namelist()
    assert "config.toml" in names and any(x.startswith("data/") for x in names)
    assert not any(x.startswith("RawImages/") for x in names)


def test_restore_rejects_zip_slip(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "pwned")
    with pytest.raises(ValueError):
        restore_backup(evil, tmp_path / "dest")
    assert not (tmp_path / "escape.txt").exists()


# -- exporters ------------------------------------------------------------
def test_letterboxd_export_uses_personal_rating_and_tags(mock_site):
    site, cfg = mock_site
    store = Store(cfg.data_dir)
    movie = next(m for m in store.collection if m.get("media_type", "movie") == "movie")
    store.corrections = {movie["id"]: {"my_rating": 9, "tags": ["Faves", "Sci-Fi"]}}
    out = cfg.data_dir / "lb.csv"
    rows = export_letterboxd(store, out)
    text = out.read_text()
    assert rows >= 1
    assert text.splitlines()[0] == "Title,Year,Rating10,WatchedDate,Tags"
    line = next(ln for ln in text.splitlines() if ln.startswith(movie["title"] + ","))
    assert ",9," in line and "Faves, Sci-Fi" in line
    # music is excluded from a Letterboxd (movies) export
    assert not any(m.get("media_type") == "music" and (m.get("title") or "") in text
                   for m in store.collection if m.get("title"))


def test_export_json_writes_full_catalog(mock_site):
    _, cfg = mock_site
    store = Store(cfg.data_dir)
    out = cfg.data_dir / "cat.json"
    n = export_json(store, out)
    data = json.loads(out.read_text())
    assert n == len(data) == len(store.collection)


def test_export_cli_format_letterboxd(mock_site, tmp_path):
    site, _ = mock_site
    out = tmp_path / "lb.csv"
    assert cli.main(["export", "--config", str(site / "config.toml"),
                     "--format", "letterboxd", "-o", str(out)]) == 0
    assert out.read_text().startswith("Title,Year,Rating10,WatchedDate,Tags")


# -- feeds ----------------------------------------------------------------
def test_feeds_emitted_and_valid(mock_site):
    _, cfg = mock_site
    feed = json.loads((cfg.data_dir / "feed.json").read_text())
    assert feed["version"].startswith("https://jsonfeed.org/version/1")
    assert feed["items"] and "title" in feed["items"][0]
    # newest-first by added_at
    rss = (cfg.data_dir / "feed.xml").read_text()
    assert rss.startswith("<?xml") and "<rss" in rss and "<item>" in rss


def test_feeds_can_be_disabled(tmp_path):
    site = tmp_path / "s"
    cli.main(["init", str(site)])
    cfg_file = site / "config.toml"
    cfg_file.write_text(cfg_file.read_text().replace("enabled  = true", "enabled  = false"))
    cli.main(["build", "--config", str(cfg_file), "--mock"])
    cfg = load_config(cfg_file)
    assert not (cfg.data_dir / "feed.json").exists()
