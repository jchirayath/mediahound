"""One-click publish — deploy the generated site to Netlify (free static hosting).

Needs a Netlify **personal access token** (netlify.com → User settings → Applications →
New access token), stored in the OS keychain as `NETLIFY_AUTH_TOKEN`. The first publish
creates a site; the id is saved in `data/.netlify-site.json` and reused after, so the URL
stays stable. Only the generated site is uploaded — `RawImages/`, `.env`, `config.toml`
and dotfiles are never sent.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote

import requests

_API = "https://api.netlify.com/api/v1"
_EXCLUDE_TOP = {"RawImages"}                 # source photos — not part of the published site
_EXCLUDE_NAMES = {".env", "config.toml"}


def _site_files(output_dir: Path) -> dict[str, Path]:
    """Map deploy-path ('/index.html', '/posters/x.jpg', …) → file on disk."""
    files: dict[str, Path] = {}
    for p in output_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(output_dir)
        if rel.parts[0] in _EXCLUDE_TOP or p.name in _EXCLUDE_NAMES:
            continue
        if any(part.startswith(".") for part in rel.parts):   # skip dotfiles/dotdirs
            continue
        files["/" + "/".join(rel.parts)] = p
    return files


def deploy(cfg, token: str, log=print) -> str:
    """Deploy the site to Netlify and return its public URL."""
    output = cfg.output_dir.resolve()
    files = _site_files(output)
    if "/index.html" not in files:
        raise RuntimeError("No index.html to publish — run a build first.")

    digests = {path: hashlib.sha1(p.read_bytes()).hexdigest() for path, p in files.items()}  # noqa: S324
    headers = {"Authorization": f"Bearer {token}"}

    # reuse the site across publishes so the link is stable
    meta_path = cfg.data_dir / ".netlify-site.json"
    site_id = None
    if meta_path.is_file():
        site_id = json.loads(meta_path.read_text(encoding="utf-8")).get("site_id")
    if not site_id:
        r = requests.post(f"{_API}/sites", headers=headers, timeout=30)
        r.raise_for_status()
        site = r.json()
        site_id = site["id"]
        meta_path.write_text(json.dumps({"site_id": site_id, "name": site.get("name")}),
                             encoding="utf-8")
        log(f"  created Netlify site: {site.get('name')}")

    # tell Netlify the file digests; it replies with the ones it still needs
    r = requests.post(f"{_API}/sites/{site_id}/deploys", headers=headers,
                      json={"files": digests}, timeout=60)
    r.raise_for_status()
    dep = r.json()
    deploy_id = dep["id"]
    required = set(dep.get("required") or [])

    # upload one file per still-needed digest
    by_digest: dict[str, Path] = {}
    for path, p in files.items():
        by_digest.setdefault(digests[path], p)
    for i, sha in enumerate(required, 1):
        p = by_digest.get(sha)
        if not p:
            continue
        rel = "/" + "/".join(p.relative_to(output).parts)
        up = requests.put(f"{_API}/deploys/{deploy_id}/files{quote(rel)}",
                          headers={**headers, "Content-Type": "application/octet-stream"},
                          data=p.read_bytes(), timeout=180)
        up.raise_for_status()
        log(f"  uploaded {i}/{len(required)}: {rel}")

    # wait until the deploy goes live
    url = dep.get("ssl_url") or dep.get("url")
    for _ in range(90):
        d = requests.get(f"{_API}/deploys/{deploy_id}", headers=headers, timeout=30).json()
        if d.get("state") == "ready":
            return d.get("ssl_url") or d.get("url") or url
        if d.get("state") == "error":
            raise RuntimeError("Netlify reported a deploy error.")
        time.sleep(1)
    return url
