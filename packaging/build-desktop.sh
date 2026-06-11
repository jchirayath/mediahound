#!/usr/bin/env bash
# Build the MediaHound desktop app locally. Run on the OS you want a build for
# (PyInstaller can't cross-compile). CI does macOS + Windows automatically — see
# .github/workflows/desktop.yml.
set -euo pipefail
cd "$(dirname "$0")/.."          # repo root

python -m pip install --upgrade pip
python -m pip install -e ".[desktop,build]"
pyinstaller --noconfirm --clean packaging/mediahound.spec

echo
echo "✅ Built into dist/:"
ls -1 dist/
echo
echo "macOS: open dist/MediaHound.app   ·   Windows: run dist/MediaHound/MediaHound.exe"
echo "Note: unsigned builds trigger a Gatekeeper/SmartScreen warning the first time —"
echo "      right-click → Open (macOS) or More info → Run anyway (Windows)."
