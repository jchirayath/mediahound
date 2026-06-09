"""Command-line entry point: `reelshelf init <dir>` and `reelshelf build`."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import load_config

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WEB_TEMPLATE = _REPO_ROOT / "web"
_CONFIG_EXAMPLE = _REPO_ROOT / "config.example.toml"

_NETLIFY_TOML = """# Deploy this folder as a static site.
[build]
  publish = "."
  command = ""
"""


def cmd_init(args) -> int:
    dest = Path(args.directory).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "RawImages").mkdir(exist_ok=True)

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

    print(f"\nInitialized ReelShelf site at {dest}")
    print("Next:")
    print(f"  1. Add cover photos to {dest / 'RawImages'}")
    print(f"  2. (optional) edit {cfg_target} to pick providers / add a .env with keys")
    print(f"  3. reelshelf build --config {cfg_target}")
    return 0


def cmd_build(args) -> int:
    from . import pipeline  # lazy: avoids importing requests/PIL for `init`
    config_path = Path(args.config).resolve()
    if not config_path.is_file():
        print(f"Config not found: {config_path}\nRun `reelshelf init <dir>` first.", file=sys.stderr)
        return 2
    cfg = load_config(config_path)
    pipeline.build(cfg, mock=args.mock, force=args.force,
                   reidentify=args.reidentify, limit=args.limit,
                   refresh_streaming=args.refresh_streaming,
                   online=args.online or args.refresh_streaming)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="reelshelf",
                                description="Catalog a DVD/VHS collection from cover photos.")
    p.add_argument("--version", action="version", version=f"reelshelf {__version__}")
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

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
