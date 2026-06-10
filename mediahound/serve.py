"""Local web server for MediaHound.

`mediahound serve` previews the generated site over http(s) (handy because browsers
block fetch() of local JSON over file://).

`mediahound serve --admin` additionally exposes a tiny, localhost-only write API so the
admin portal can save edits **straight into data/corrections.json** (and seen-overrides /
identify-queue) — no "Export changes → drop file in → rebuild" dance. Edits persist
immediately and therefore survive every future `mediahound build`.

Security model: the write API is bound to 127.0.0.1 by default and rejects cross-origin
requests (Origin must match the server). It is a local authoring tool, not a public
endpoint — never expose it on a public interface.
"""
from __future__ import annotations

import json
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Config

_MAX_BODY = 8 * 1024 * 1024  # 8 MB cap on a write payload


def _merge(existing: dict, patch: dict) -> dict:
    """Deep-ish merge: per-id dicts are merged (patch wins per field); other values replace."""
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in existing.items()}
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


class _Handler(SimpleHTTPRequestHandler):
    # set by make_handler():
    admin: bool = False
    cfg: Config = None
    allowed_origins: set = frozenset()
    log_fn = staticmethod(lambda *_: None)

    # -- helpers ----------------------------------------------------------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:           # non-browser client (curl) or same-origin GET
            return True
        return origin in self.allowed_origins

    def _read_json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > _MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def _data_path(self, name: str) -> Path:
        return self.cfg.data_dir / name

    def _write_data(self, name: str, obj) -> None:
        p = self._data_path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

    def _read_data(self, name: str, default):
        p = self._data_path(name)
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return default
        return default

    # quieter logging
    def log_message(self, fmt, *args):
        self.log_fn(f"  {self.address_string()} - {fmt % args}")

    # -- routes -----------------------------------------------------------
    def do_GET(self):
        if self.path.rstrip("/") == "/api/ping":
            from . import __version__
            return self._send_json({"ok": True, "admin": self.admin,
                                    "app": "mediahound", "version": __version__})
        return super().do_GET()

    def do_POST(self):
        route = self.path.split("?", 1)[0].rstrip("/")
        if not self.admin or not route.startswith("/api/"):
            return self._send_json({"ok": False, "error": "not found"}, 404)
        if not self._origin_ok():
            return self._send_json({"ok": False, "error": "cross-origin write refused"}, 403)

        if route == "/api/corrections":
            return self._merge_file("corrections.json", "corrections")
        if route == "/api/seen":
            return self._replace_file("seen-overrides.json", "seen overrides")
        if route == "/api/identify":
            return self._merge_file("identify-queue.json", "identify queue")
        if route == "/api/rebuild":
            return self._rebuild()
        return self._send_json({"ok": False, "error": "unknown endpoint"}, 404)

    # -- handlers ---------------------------------------------------------
    def _merge_file(self, name: str, label: str):
        patch = self._read_json_body()
        if not isinstance(patch, dict):
            return self._send_json({"ok": False, "error": "expected a JSON object"}, 400)
        merged = _merge(self._read_data(name, {}), patch)
        self._write_data(name, merged)
        self.log_fn(f"  saved {len(patch)} {label} edit(s) → data/{name} ({len(merged)} total)")
        return self._send_json({"ok": True, "saved": len(patch), "total": len(merged)})

    def _replace_file(self, name: str, label: str):
        body = self._read_json_body()
        if not isinstance(body, dict):
            return self._send_json({"ok": False, "error": "expected a JSON object"}, 400)
        self._write_data(name, body)
        self.log_fn(f"  saved {len(body)} {label} → data/{name}")
        return self._send_json({"ok": True, "total": len(body)})

    def _rebuild(self):
        try:
            from . import pipeline
            pipeline.build(self.cfg, online=False, log=lambda m: self.log_fn(m))
            return self._send_json({"ok": True, "rebuilt": True})
        except Exception as exc:                       # noqa: BLE001 - report to client
            self.log_fn(f"  rebuild failed: {exc}")
            return self._send_json({"ok": False, "error": str(exc)}, 500)


def make_handler(cfg: Config, admin: bool, origins: set, log_fn):
    return type("MediaHoundHandler", (_Handler,), {
        "admin": admin, "cfg": cfg, "allowed_origins": frozenset(origins),
        "log_fn": staticmethod(log_fn),
    })


def serve(cfg: Config, host: str = "127.0.0.1", port: int = 8765,
          admin: bool = False, open_browser: bool = True, log=print) -> int:
    site = cfg.output_dir.resolve()
    if not (site / "index.html").is_file():
        log(f"No index.html in {site} — run `mediahound build` first.")
        return 2

    origins = {f"http://{host}:{port}", f"http://localhost:{port}", f"http://127.0.0.1:{port}"}
    handler = partial(make_handler(cfg, admin, origins, log), directory=str(site))
    httpd = ThreadingHTTPServer((host, port), handler)

    url = f"http://{host}:{port}/"
    mode = "ADMIN (edits save straight to data/)" if admin else "read-only preview"
    log(f"MediaHound serving {site}")
    log(f"  → {url}   [{mode}]")
    if admin:
        log("  Admin writes are localhost-only. Unlock the portal with your admin password,")
        log("  then your title/format/delete/seen edits persist to data/ automatically and")
        log("  survive every future `mediahound build`.")
    log("  Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("\nStopped.")
    finally:
        httpd.server_close()
    return 0
