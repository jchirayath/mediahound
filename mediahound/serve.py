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

import hmac
import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import Config

_MAX_BODY = 8 * 1024 * 1024         # 8 MB cap on a JSON write payload
_MAX_UPLOAD = 40 * 1024 * 1024      # 40 MB cap for a single photo upload (base64-inflated)


def _lan_ip() -> str:
    """Best-effort local-network IP (for phone mode). Never sends traffic."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))            # picks the right interface; no packets sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _print_qr(url: str, log) -> None:
    """Print a scannable QR for `url` to the terminal (falls back to the URL alone)."""
    try:
        import io

        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        log(buf.getvalue())
    except Exception:                          # noqa: BLE001 - qrcode optional
        log("  (install the `qrcode` package to show a scannable code)")


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
    token: str | None = None          # phone mode: a shared secret required on every write
    site_dir: str = "."               # served document root (switchable at runtime via the library switcher)
    log_fn = staticmethod(lambda *_: None)

    # Serve static files from the (mutable) class `site_dir`, so the library switcher can
    # re-point a running server at a different library without restarting it.
    def translate_path(self, path):
        self.directory = type(self).site_dir
        return super().translate_path(path)

    # Never let the app shell (HTML/JS/CSS) be stale-cached by the webview or browser — otherwise
    # an upgraded MediaHound keeps running the old UI (the desktop WebKit view caches aggressively).
    # Force revalidation on the code files; posters/images may still cache normally.
    def end_headers(self):
        route = self.path.split("?", 1)[0]
        if route.endswith((".html", ".js", ".css", "/")) or route == "":
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

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

    def _token_ok(self) -> bool:
        # No token configured (localhost-only mode) → the loopback bind is the protection.
        # Token configured (phone/LAN mode) → require it on every write (constant-time compare).
        if not self.token:
            return True
        given = self.headers.get("X-MediaHound-Token") or ""
        return hmac.compare_digest(given, self.token)

    def _read_json_body(self, max_bytes: int = _MAX_BODY):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > max_bytes:
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
        route = self.path.split("?", 1)[0].rstrip("/")
        if route == "/api/ping":
            from . import __version__
            return self._send_json({"ok": True, "admin": self.admin, "app": "mediahound",
                                    "version": __version__, "phone": bool(self.token)})
        if route == "/api/keys":
            if not self.admin:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            from . import keystore
            return self._send_json({"ok": True, "keys": keystore.status()})  # booleans only
        if route == "/api/libraries":
            if not self.admin:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            if self.token:                     # switching libraries is a local-only operation
                return self._send_json({"ok": True, "switchable": False, "recent": [],
                                        "current": {"path": str(self.cfg.base_dir),
                                                    "title": self.cfg.site.get("title")}})
            from . import libraries
            return self._send_json({"ok": True, "switchable": True,
                                    "current": {"path": str(self.cfg.base_dir),
                                                "title": self.cfg.site.get("title")},
                                    "recent": libraries.list_recent()})
        if route == "/api/backup":
            if not self.admin:
                return self._send_json({"ok": False, "error": "not found"}, 404)
            if self.token:                     # a full-library download is localhost-only, never over the LAN
                return self._send_json({"ok": False, "error": "Back up from the computer running MediaHound"}, 403)
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            return self._backup(no_photos="no_photos" in query)
        return super().do_GET()

    def do_POST(self):
        route = self.path.split("?", 1)[0].rstrip("/")
        if not self.admin or not route.startswith("/api/"):
            return self._send_json({"ok": False, "error": "not found"}, 404)
        if not self._origin_ok():
            return self._send_json({"ok": False, "error": "cross-origin write refused"}, 403)
        if not self._token_ok():
            return self._send_json({"ok": False, "error": "missing or invalid access token"}, 403)

        if route == "/api/corrections":
            return self._merge_file("corrections.json", "corrections")
        if route == "/api/loans":
            return self._replace_file("loans.json", "loans")
        if route == "/api/seen":
            return self._replace_file("seen-overrides.json", "seen overrides")
        if route == "/api/identify":
            return self._merge_file("identify-queue.json", "identify queue")
        if route == "/api/rebuild":
            return self._rebuild()
        if route == "/api/import":
            return self._import()
        if route == "/api/import-discogs":
            if self.token:                     # uses your Discogs token / collection — localhost only
                return self._send_json(
                    {"ok": False, "error": "Import Discogs from the computer running MediaHound"}, 403)
            return self._import_discogs()
        if route == "/api/upload":
            return self._upload()
        if route == "/api/identify-barcode":
            return self._identify_barcode()
        if route in ("/api/switch-library", "/api/create-library"):
            if self.token:                     # local-only: never switch the served library over the LAN
                return self._send_json(
                    {"ok": False, "error": "Switch libraries from the computer running MediaHound"}, 403)
            return self._switch_library(create=route.endswith("create-library"))
        if route == "/api/keys":
            # API keys are set from THIS computer only — never accept them over the LAN.
            if self.token:
                return self._send_json(
                    {"ok": False, "error": "API keys can only be set on the computer running MediaHound"}, 403)
            return self._set_keys()
        if route == "/api/publish":
            if self.token:                     # publishing uses your Netlify token — localhost only
                return self._send_json(
                    {"ok": False, "error": "Publish from the computer running MediaHound"}, 403)
            return self._publish()
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

    def _import(self):
        """Bulk-add titles from a pasted/uploaded CSV, then regenerate the site."""
        import os
        import tempfile
        body = self._read_json_body()
        if not isinstance(body, dict) or not isinstance(body.get("csv"), str) or not body["csv"].strip():
            return self._send_json({"ok": False, "error": "expected {csv: <text>}"}, 400)
        online = bool(body.get("online"))
        tmp = None
        try:
            from . import pipeline
            from .csvio import import_csv
            from .store import Store
            store = Store(self.cfg.data_dir)
            fd, tmp = tempfile.mkstemp(suffix=".csv")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body["csv"])
            added, enriched = import_csv(self.cfg, store, Path(tmp), online, self.log_fn)
            store.save()
            pipeline._write_site(self.cfg, store)
            return self._send_json({"ok": True, "added": added, "enriched": enriched})
        except Exception as exc:                       # noqa: BLE001 - report to client
            self.log_fn(f"  import failed: {exc}")
            return self._send_json({"ok": False, "error": str(exc)}, 500)
        finally:
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _upload(self):
        """Save one dropped cover photo into RawImages/<video|audio>. The client uploads
        files one at a time (base64), then calls /api/rebuild to catalog them."""
        import base64
        import io
        import os
        import re

        from .store import IMAGE_EXTS
        body = self._read_json_body(max_bytes=_MAX_UPLOAD)
        if not isinstance(body, dict) or not isinstance(body.get("data"), str):
            return self._send_json({"ok": False, "error": "expected {filename, media_type, data}"}, 400)
        media_type = "music" if body.get("media_type") == "music" else "movie"
        sub = "audio" if media_type == "music" else "video"
        # sanitise the filename → a safe basename with an image extension
        raw_name = os.path.basename(str(body.get("filename") or "photo.jpg")).strip()
        stem, ext = os.path.splitext(raw_name)
        stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem) or "photo"
        if ext.lower() not in IMAGE_EXTS:
            return self._send_json({"ok": False, "error": f"unsupported file type: {ext!r}"}, 400)
        try:
            blob = base64.b64decode(body["data"], validate=True)
        except Exception:                              # noqa: BLE001
            return self._send_json({"ok": False, "error": "bad base64 data"}, 400)
        # verify it's a real image before writing anything to disk
        try:
            from PIL import Image
            Image.open(io.BytesIO(blob)).verify()
        except Exception:                              # noqa: BLE001
            return self._send_json({"ok": False, "error": "not a valid image"}, 400)
        dest_dir = (self.cfg.input_dir / sub)
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / f"{stem}{ext.lower()}"
        i = 1
        while target.exists():                         # never clobber an existing photo
            target = dest_dir / f"{stem}-{i}{ext.lower()}"
            i += 1
        target.write_bytes(blob)
        self.log_fn(f"  uploaded {target.name} → RawImages/{sub}/")
        return self._send_json({"ok": True, "saved": target.name, "media_type": media_type})

    def _switch_library(self, create: bool = False):
        """Re-point the running admin server at a different library (or create one), so the user
        can switch catalogs from the UI without restarting. Localhost-only; updates the recents."""
        import argparse
        body = self._read_json_body()
        raw = (isinstance(body, dict) and str(body.get("path") or "").strip()) or ""
        if not raw:
            return self._send_json({"ok": False, "error": "expected {path: <library folder>}"}, 400)
        target = Path(raw).expanduser()
        try:
            from . import libraries, pipeline
            from .cli import cmd_init
            from .config import load_config
            if create:
                if libraries.is_library(target):
                    return self._send_json({"ok": False, "error": "a library already exists there"}, 400)
                cmd_init(argparse.Namespace(directory=str(target), force=False))
            config_path = target / "config.toml"
            if not config_path.is_file():
                return self._send_json(
                    {"ok": False, "error": f"no config.toml in {target} — not a MediaHound library"}, 400)
            new_cfg = load_config(config_path)
            if not (new_cfg.data_dir / "collection.json").is_file():
                pipeline.build(new_cfg, online=False, log=self.log_fn)   # ensure there's a site to serve
            # swap the served library for every subsequent request (shared class attributes)
            cls = type(self)
            cls.cfg = new_cfg
            cls.site_dir = str(new_cfg.output_dir.resolve())
            libraries.add_recent(new_cfg.base_dir, new_cfg.site.get("title"))
            self.log_fn(f"  switched library → {new_cfg.base_dir}")
            return self._send_json({"ok": True, "title": new_cfg.site.get("title"),
                                    "path": str(new_cfg.base_dir)})
        except Exception as exc:                       # noqa: BLE001 - report to client
            self.log_fn(f"  switch library failed: {exc}")
            return self._send_json({"ok": False, "error": str(exc)}, 500)

    def _identify_barcode(self):
        """Resolve a scanned UPC/EAN to a release/title and add it to the catalog (one-tap add)."""
        import os
        import tempfile
        body = self._read_json_body()
        upc = (isinstance(body, dict) and str(body.get("upc") or "").strip()) or ""
        if not upc.isdigit():
            return self._send_json({"ok": False, "error": "expected {upc: <digits>, media_type}"}, 400)
        media_type = "music" if (isinstance(body, dict) and body.get("media_type") == "music") else "movie"
        tmp = None
        try:
            from . import barcode, pipeline
            from .store import Store
            match = barcode.lookup(self.cfg, upc, media_type)
            if not match:
                return self._send_json({"ok": True, "matched": False, "upc": upc})
            store = Store(self.cfg.data_dir)
            if media_type == "music":
                item = barcode.music_item_from_meta(self.cfg, match["meta"], upc)
                store.upsert_movie(item)
                store.record(f"barcode-{upc}", item["source_image"], "identified",
                             item["id"], pipeline._now())
                store.save()
                pipeline._write_site(self.cfg, store)
                return self._send_json({"ok": True, "matched": True, "media_type": "music",
                                        "title": item["title"], "artist": item.get("artist"),
                                        "year": item.get("year")})
            # movie: resolve UPC → product title, then enrich via the normal title path
            from .csvio import import_csv
            fd, tmp = tempfile.mkstemp(suffix=".csv")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write("media_type,title\nmovie," + match["title"].replace(",", " ") + "\n")
            import_csv(self.cfg, store, Path(tmp), online=True, log=self.log_fn)
            store.save()
            pipeline._write_site(self.cfg, store)
            return self._send_json({"ok": True, "matched": True, "media_type": "movie",
                                    "title": match["title"]})
        except Exception as exc:                       # noqa: BLE001 - report to client
            self.log_fn(f"  barcode identify failed: {exc}")
            return self._send_json({"ok": False, "error": str(exc)}, 500)
        finally:
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _import_discogs(self):
        """Import a Discogs user's collection, then regenerate the site."""
        body = self._read_json_body()
        username = (isinstance(body, dict) and str(body.get("username") or "").strip()) or ""
        if not username:
            return self._send_json({"ok": False, "error": "expected {username: <discogs user>}"}, 400)
        online = bool(body.get("online", True))
        try:
            from . import keystore, pipeline
            from .discogs_import import import_collection
            from .store import Store
            token = keystore.get_key("DISCOGS_TOKEN")
            store = Store(self.cfg.data_dir)
            added, enriched = import_collection(self.cfg, store, username, token=token,
                                                online=online, log=self.log_fn)
            store.save()
            pipeline._write_site(self.cfg, store)
            return self._send_json({"ok": True, "added": added, "enriched": enriched})
        except Exception as exc:                       # noqa: BLE001 - report to client
            self.log_fn(f"  discogs import failed: {exc}")
            return self._send_json({"ok": False, "error": str(exc)}, 500)

    def _backup(self, no_photos: bool = False):
        """Stream a zip backup of the whole library as a download."""
        import os
        import tempfile
        tmp = None
        try:
            from . import backup
            fd, tmp = tempfile.mkstemp(suffix=".zip")
            os.close(fd)
            n = backup.make_backup(self.cfg, Path(tmp), no_photos=no_photos)
            blob = Path(tmp).read_bytes()
            label = "library" + ("-data" if no_photos else "")
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Content-Disposition", f'attachment; filename="mediahound-{label}.zip"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(blob)
            self.log_fn(f"  backup: {n} file(s){' (data-only)' if no_photos else ''} downloaded")
        except Exception as exc:                       # noqa: BLE001 - report to client
            self.log_fn(f"  backup failed: {exc}")
            self._send_json({"ok": False, "error": str(exc)}, 500)
        finally:
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _set_keys(self):
        """Store provider API keys in the OS keychain. Values are write-only (never read back)."""
        from . import keystore
        body = self._read_json_body()
        if not isinstance(body, dict):
            return self._send_json({"ok": False, "error": "expected a JSON object"}, 400)
        changed = []
        for name, value in body.items():
            if name in keystore.KEY_NAMES:
                if keystore.set_key(name, (str(value) if value else "").strip() or None):
                    changed.append(name)
        if changed:
            self.log_fn(f"  saved API key(s) to the OS keychain: {', '.join(changed)}")
        else:
            self.log_fn("  API key save requested but the keychain backend is unavailable")
        return self._send_json({"ok": bool(changed), "changed": changed, "keys": keystore.status()})

    def _publish(self):
        """Deploy the generated site to Netlify and return its public URL."""
        from . import keystore
        body = self._read_json_body() or {}
        token = (body.get("token") or "").strip()
        if token:                              # a token sent from the UI → save it for next time
            keystore.set_key("NETLIFY_AUTH_TOKEN", token)
        token = token or keystore.get_key("NETLIFY_AUTH_TOKEN")
        if not token:
            return self._send_json({"ok": False, "need_token": True,
                                    "error": "A Netlify access token is required to publish."}, 200)
        try:
            from . import publish
            url = publish.deploy(self.cfg, token, log=self.log_fn)
            self.log_fn(f"  published → {url}")
            return self._send_json({"ok": True, "url": url})
        except Exception as exc:               # noqa: BLE001 - report to the client
            self.log_fn(f"  publish failed: {exc}")
            return self._send_json({"ok": False, "error": str(exc)}, 502)


def make_handler(cfg: Config, admin: bool, origins: set, log_fn, token: str | None = None,
                 site_dir: str | None = None):
    return type("MediaHoundHandler", (_Handler,), {
        "admin": admin, "cfg": cfg, "allowed_origins": frozenset(origins),
        "token": token, "site_dir": site_dir or str(cfg.output_dir.resolve()),
        "log_fn": staticmethod(log_fn),
    })


def serve(cfg: Config, host: str = "127.0.0.1", port: int = 8765, admin: bool = False,
          open_browser: bool = True, log=print, phone: bool = False) -> int:
    """Serve the site. `phone=True` enables LAN access for uploading from a phone:
    binds to all interfaces, prints a QR code, and **token-gates every write** so only the
    device that scanned the code can edit."""
    site = cfg.output_dir.resolve()
    if not (site / "index.html").is_file():
        log(f"No index.html in {site} — run `mediahound build` first.")
        return 2

    token = None
    lan = _lan_ip()
    if phone:
        import secrets
        host = "0.0.0.0"                       # noqa: S104 - intentional LAN bind for phone mode
        token = secrets.token_urlsafe(16)

    origins = {f"http://{host}:{port}", f"http://localhost:{port}", f"http://127.0.0.1:{port}",
               f"http://{lan}:{port}"}
    handler = make_handler(cfg, admin, origins, log, token, site_dir=str(site))
    httpd = ThreadingHTTPServer((host, port), handler)
    # Remember this library so the switcher can offer it again (admin, non-phone sessions only).
    if admin and not token:
        try:
            from . import libraries
            libraries.add_recent(cfg.base_dir, cfg.site.get("title"))
        except Exception:                          # noqa: BLE001 - recents are best-effort
            pass

    local_url = f"http://127.0.0.1:{port}/" + (f"?t={token}" if token else "")
    mode = "ADMIN (edits save straight to data/)" if admin else "read-only preview"
    log(f"MediaHound serving {site}")
    log(f"  → http://127.0.0.1:{port}/   [{mode}]")
    if phone:
        phone_url = f"http://{lan}:{port}/?t={token}"
        log("")
        log("  📱 PHONE MODE — scan this with your phone (same Wi-Fi) to add photos from it:")
        log("")
        _print_qr(phone_url, log)
        log(f"     {phone_url}")
        log("  ⚠️  This opens the editor to your local network. Only share the code with people")
        log("     you trust, and only on a trusted Wi-Fi. The token protects edits; stop with Ctrl+C.")
    elif admin:
        log("  Admin writes are localhost-only; edits persist to data/ and survive every rebuild.")
    log("  Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(local_url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("\nStopped.")
    finally:
        httpd.server_close()
    return 0
