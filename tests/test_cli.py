"""CLI end-to-end: init scaffolds a site, build --mock generates the catalog."""
import pytest

from reelshelf import cli


def test_init_then_mock_build(tmp_path):
    site = tmp_path / "site"
    assert cli.main(["init", str(site)]) == 0
    assert (site / "index.html").is_file()
    assert (site / "config.toml").is_file()
    assert (site / "RawImages").is_dir()

    rc = cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    assert rc == 0
    assert (site / "data" / "collection.json").is_file()
    assert (site / "data" / "bundle.js").is_file()


def test_build_missing_config_returns_error(tmp_path):
    assert cli.main(["build", "--config", str(tmp_path / "nope.toml"), "--mock"]) == 2


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert "reelshelf" in capsys.readouterr().out
