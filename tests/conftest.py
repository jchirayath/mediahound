"""Shared test helpers — no network is ever made; HTTP is monkeypatched."""
import pytest
import requests


@pytest.fixture(autouse=True)
def _isolated_app_config(tmp_path, monkeypatch):
    """Point per-user app config (the library recents file) at a throwaway dir so the suite
    never reads or writes the developer's real ~/.config/mediahound/. Any test that starts an
    admin server records a recent — without this, those paths would leak into the real file."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "_appcfg"))


@pytest.fixture
def mem_keyring():
    """Swap in an in-memory keyring so tests never touch the real OS keychain."""
    import keyring
    from keyring.backend import KeyringBackend

    class _Mem(KeyringBackend):
        priority = 1

        def __init__(self):
            super().__init__()
            self._d = {}

        def get_password(self, service, username):
            return self._d.get((service, username))

        def set_password(self, service, username, password):
            self._d[(service, username)] = password

        def delete_password(self, service, username):
            self._d.pop((service, username), None)

    prev = keyring.get_keyring()
    keyring.set_keyring(_Mem())
    yield
    keyring.set_keyring(prev)


class FakeResp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, json_data, status=200):
        self._json = json_data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        if isinstance(self._json, Exception):
            raise self._json
        return self._json


def make_image(path, w, h, color=(120, 120, 120)):
    from PIL import Image
    Image.new("RGB", (w, h), color).save(path, "JPEG")
    return path
