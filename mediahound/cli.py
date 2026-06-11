"""Command-line entry point: `mediahound init <dir>` and `mediahound build`."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import load_config

# Template assets are bundled inside the package so `pip install mediahound` is self-contained.
_PKG_DIR = Path(__file__).resolve().parent
_WEB_TEMPLATE = _PKG_DIR / "web"
_CONFIG_EXAMPLE = _PKG_DIR / "config.example.toml"

_NETLIFY_TOML = """# Deploy this folder as a static site.
[build]
  publish = "."
  command = ""
"""


def cmd_init(args) -> int:
    dest = Path(args.directory).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    # Raw-image folders, split by media type: video → movies, audio → music.
    (dest / "RawImages").mkdir(exist_ok=True)
    for sub in ("video", "audio"):
        (dest / "RawImages" / sub).mkdir(exist_ok=True)
    (dest / "RawImages" / "README.txt").write_text(
        "Put cover photos here, sorted by media type:\n"
        "  RawImages/video/  → movies (DVD, VHS, Blu-ray, LaserDisc)\n"
        "  RawImages/audio/  → music  (CD, vinyl, cassette)\n"
        "Photos left directly in RawImages/ are treated as video (movies).\n",
        encoding="utf-8")

    # Copy the static site template.
    for item in _WEB_TEMPLATE.iterdir():
        target = dest / item.name
        if target.exists() and not args.force:
            print(f"  skip (exists): {target.name}")
            continue
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
        print(f"  + {target.relative_to(dest)}")

    # config.toml from the example (never overwrite a real one).
    cfg_target = dest / "config.toml"
    if not cfg_target.exists() or args.force:
        shutil.copy2(_CONFIG_EXAMPLE, cfg_target)
        print("  + config.toml")
    netlify = dest / "netlify.toml"
    if not netlify.exists():
        netlify.write_text(_NETLIFY_TOML, encoding="utf-8")
        print("  + netlify.toml")

    print(f"\nInitialized MediaHound site at {dest}")
    print("Next:")
    print(f"  1. Add cover photos: movies → {dest / 'RawImages' / 'video'}, "
          f"music → {dest / 'RawImages' / 'audio'}")
    print(f"  2. (optional) edit {cfg_target} to pick providers / add a .env with keys")
    print(f"  3. mediahound build --config {cfg_target} --online")
    return 0


def cmd_build(args) -> int:
    from . import pipeline  # lazy: avoids importing requests/PIL for `init`
    config_path = Path(args.config).resolve()
    if not config_path.is_file():
        print(f"Config not found: {config_path}\nRun `mediahound init <dir>` first.", file=sys.stderr)
        return 2
    cfg = load_config(config_path)
    pipeline.build(cfg, mock=args.mock, force=args.force,
                   reidentify=args.reidentify, limit=args.limit,
                   refresh_streaming=args.refresh_streaming,
                   online=args.online or args.refresh_streaming)
    return 0


def _load_or_die(config_arg: str):
    config_path = Path(config_arg).resolve()
    if not config_path.is_file():
        print(f"Config not found: {config_path}\nRun `mediahound init <dir>` first.", file=sys.stderr)
        sys.exit(2)
    return load_config(config_path)


def cmd_import(args) -> int:
    from . import pipeline
    from .csvio import import_csv
    from .store import Store
    cfg = _load_or_die(args.config)
    csv_path = Path(args.file).resolve()
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 2
    store = Store(cfg.data_dir)
    import_csv(cfg, store, csv_path, online=args.online, log=print)
    store.save()
    pipeline._write_site(cfg, store)
    print(f"Done. Catalog written to {cfg.data_dir}")
    return 0


def cmd_export(args) -> int:
    from .csvio import export_csv
    from .store import Store
    cfg = _load_or_die(args.config)
    store = Store(cfg.data_dir)
    out = Path(args.output).resolve()
    n = export_csv(store, out)
    print(f"Exported {n} item(s) → {out}")
    return 0


def cmd_serve(args) -> int:
    from . import serve as serve_mod
    cfg = _load_or_die(args.config)
    return serve_mod.serve(cfg, host=args.host, port=args.port, admin=args.admin,
                           open_browser=not args.no_open)


def cmd_app(args) -> int:
    """One command for non-technical users: set up the folder if needed, then open the editor."""
    from . import pipeline
    from . import serve as serve_mod
    site = Path(args.directory).resolve()
    config_path = site / "config.toml"
    if not config_path.is_file():
        print(f"Setting up a new MediaHound library at {site} …")
        cmd_init(argparse.Namespace(directory=str(site), force=False))
        print()
    cfg = load_config(config_path)
    # make sure there's a catalog to open (an empty one is fine — the welcome screen guides you)
    if not (cfg.data_dir / "collection.json").is_file():
        pipeline.build(cfg, online=False, log=print)
    return serve_mod.serve(cfg, host=args.host, port=args.port, admin=True,
                           open_browser=not args.no_open, phone=args.phone)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mediahound",
                                description="Catalog a movie & music collection from cover photos or CSV.")
    p.add_argument("--version", action="version", version=f"mediahound {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="scaffold a new site folder (template + config).")
    pi.add_argument("directory", help="target site folder")
    pi.add_argument("--force", action="store_true", help="overwrite existing template files")
    pi.set_defaults(func=cmd_init)

    pb = sub.add_parser("build", help="process new images and (re)generate the catalog.")
    pb.add_argument("--config", default="config.toml", help="path to config.toml (default ./config.toml)")
    pb.add_argument("--mock", action="store_true", help="demo with sample data; no providers/keys needed")
    pb.add_argument("--force", action="store_true", help="reprocess every image, not just new ones")
    pb.add_argument("--reidentify", metavar="HASH", help="reprocess a single image by its sha256")
    pb.add_argument("--limit", type=int, help="process at most N new images this run")
    pb.add_argument("--online", action="store_true",
                    help="allow calls to online databases (metadata, where-to-watch). "
                         "Default is OFFLINE: regenerate the site from existing data only.")
    pb.add_argument("--refresh-streaming", action="store_true",
                    help="re-check where-to-watch for every title (implies --online)")
    pb.set_defaults(func=cmd_build)

    pm = sub.add_parser("import", help="bulk-add items from a CSV (no photos needed).")
    pm.add_argument("file", help="path to the CSV file")
    pm.add_argument("--config", default="config.toml", help="path to config.toml")
    pm.add_argument("--online", action="store_true",
                    help="enrich each row (cover art + missing fields) via the metadata providers")
    pm.set_defaults(func=cmd_import)

    pe = sub.add_parser("export", help="write the whole catalog to a CSV (backup/migration).")
    pe.add_argument("--config", default="config.toml", help="path to config.toml")
    pe.add_argument("-o", "--output", default="catalog.csv", help="output CSV path")
    pe.set_defaults(func=cmd_export)

    ps = sub.add_parser("serve", help="preview the site locally; --admin saves edits straight to data/.")
    ps.add_argument("--config", default="config.toml", help="path to config.toml")
    ps.add_argument("--admin", action="store_true",
                    help="enable the localhost write API: portal edits persist to "
                         "data/corrections.json automatically (survive every rebuild).")
    ps.add_argument("--port", type=int, default=8765, help="port (default 8765)")
    ps.add_argument("--host", default="127.0.0.1",
                    help="bind address (default 127.0.0.1; admin writes should stay localhost)")
    ps.add_argument("--no-open", action="store_true", help="don't open a browser window")
    ps.set_defaults(func=cmd_serve)

    pa = sub.add_parser("app",
                        help="the easy button: set up a library (if needed) and open the editor in "
                             "your browser — no other commands to remember.")
    pa.add_argument("directory", nargs="?", default="MediaHound-Library",
                    help="library folder (created if missing; default ./MediaHound-Library)")
    pa.add_argument("--phone", action="store_true",
                    help="let your phone add photos: open to your Wi-Fi and show a QR code to scan "
                         "(uploads are token-protected). Use on a trusted network only.")
    pa.add_argument("--port", type=int, default=8765, help="port (default 8765)")
    pa.add_argument("--host", default="127.0.0.1", help="bind address (keep on localhost)")
    pa.add_argument("--no-open", action="store_true", help="don't open a browser window")
    pa.set_defaults(func=cmd_app)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
