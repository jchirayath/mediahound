"""Shared test helpers — no network is ever made; HTTP is monkeypatched."""
import requests


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
