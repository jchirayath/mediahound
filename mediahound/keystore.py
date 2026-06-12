"""Secure provider-key storage in the OS keychain (macOS Keychain / Windows Credential
Manager / Linux Secret Service), via the `keyring` library.

Keys set through the admin console (TMDB / OMDb / Anthropic) are written here — never to a
file in plaintext. At build time `load_into_env()` fills any *unset* key env var from the
keychain, so providers (which read `os.environ`) work transparently. Precedence:
real environment > the instance `.env` > the keychain.

If `keyring` isn't installed or has no working backend, every call degrades gracefully to a
no-op (the feature is simply unavailable; nothing crashes).
"""
from __future__ import annotations

import os

_SERVICE = "mediahound"

# Metadata provider keys — these are the ones surfaced in the admin "API keys" panel.
KEY_NAMES = ("TMDB_API_KEY", "OMDB_API_KEY", "ANTHROPIC_API_KEY", "DISCOGS_TOKEN")
# Every name that may be stored at all (publish token included) — guards arbitrary writes.
_ALLOWED = (*KEY_NAMES, "NETLIFY_AUTH_TOKEN")


def _keyring():
    import keyring  # imported lazily so the package works without it installed
    return keyring


def get_key(name: str) -> str | None:
    if name not in _ALLOWED:
        return None
    try:
        return _keyring().get_password(_SERVICE, name)
    except Exception:                          # noqa: BLE001 - missing backend/lib → unavailable
        return None


def set_key(name: str, value: str | None) -> bool:
    """Store (or, if value is falsy, delete) a key. Returns True on success."""
    if name not in _ALLOWED:
        return False
    try:
        kr = _keyring()
        if value:
            kr.set_password(_SERVICE, name, value)
        else:
            try:
                kr.delete_password(_SERVICE, name)
            except Exception:                  # noqa: BLE001 - nothing to delete is fine
                pass
        return True
    except Exception:                          # noqa: BLE001 - no backend/lib
        return False


def status() -> dict[str, bool]:
    """Which keys are set — booleans only, never the values."""
    return {name: bool(get_key(name)) for name in KEY_NAMES}


def load_into_env() -> None:
    """Fill any unset key env vars from the keychain (env/.env keep precedence)."""
    for name in KEY_NAMES:
        if not os.environ.get(name):
            value = get_key(name)
            if value:
                os.environ[name] = value
