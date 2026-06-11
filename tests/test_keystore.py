"""Keystore: keys go to the OS keychain (mocked in tests), only known names, and fill the
env at build time without overriding real env/.env."""
import os

from mediahound import keystore


def test_set_get_status(mem_keyring):
    assert keystore.status() == {n: False for n in keystore.KEY_NAMES}
    assert keystore.set_key("TMDB_API_KEY", "abc123") is True
    assert keystore.get_key("TMDB_API_KEY") == "abc123"
    assert keystore.status()["TMDB_API_KEY"] is True
    # blank value deletes
    assert keystore.set_key("TMDB_API_KEY", None) is True
    assert keystore.get_key("TMDB_API_KEY") is None


def test_unknown_names_are_rejected(mem_keyring):
    assert keystore.set_key("EVIL_KEY", "x") is False
    assert keystore.get_key("EVIL_KEY") is None


def test_load_into_env_fills_unset_only(mem_keyring, monkeypatch):
    keystore.set_key("OMDB_API_KEY", "from-keychain")
    keystore.set_key("TMDB_API_KEY", "kc-tmdb")
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    monkeypatch.setenv("TMDB_API_KEY", "from-env")     # real env must win
    keystore.load_into_env()
    assert os.environ["OMDB_API_KEY"] == "from-keychain"   # filled
    assert os.environ["TMDB_API_KEY"] == "from-env"        # not overridden
