"""Desktop app: library setup is headless-safe; the GUI entry point doesn't need a display
to scaffold/build (the native window only opens in `run()`, which we don't start here)."""
from pathlib import Path

import pytest

from mediahound import cli, desktop


def test_prepare_scaffolds_and_builds_an_empty_library(tmp_path):
    lib = tmp_path / "Lib"
    cfg = desktop.prepare(str(lib), log=lambda *_: None)
    assert (lib / "config.toml").is_file()                     # scaffolded
    assert (lib / "index.html").is_file()                      # web template bundled
    assert (cfg.data_dir / "collection.json").is_file()        # an (empty) catalog exists
    import json
    assert json.loads((cfg.data_dir / "collection.json").read_text()) == []


def test_prepare_is_idempotent(tmp_path):
    lib = tmp_path / "Lib"
    desktop.prepare(str(lib), log=lambda *_: None)
    cfg = desktop.prepare(str(lib), log=lambda *_: None)       # second run: no error, same library
    assert (cfg.data_dir / "collection.json").is_file()


def test_default_library_under_home():
    assert desktop.default_library().parent == Path.home()


def test_gui_subcommand_is_registered():
    with pytest.raises(SystemExit) as e:
        cli.main(["gui", "--help"])
    assert e.value.code == 0
