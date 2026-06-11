# PyInstaller spec — build the MediaHound desktop app (.app on macOS, folder/.exe on Windows).
#
#   pip install -e ".[desktop,build]"
#   pyinstaller --noconfirm --clean packaging/mediahound.spec
#
# Output: dist/MediaHound (Windows folder with MediaHound.exe) or dist/MediaHound.app (macOS).
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))          # noqa: F821 - SPECPATH is injected
PKG = os.path.join(ROOT, "mediahound")

# Bundle the web template + example config at the same package-relative paths the code expects
# (cli.py resolves _PKG_DIR / "web" and _PKG_DIR / "config.example.toml" at runtime).
datas = [
    (os.path.join(PKG, "web"), "mediahound/web"),
    (os.path.join(PKG, "config.example.toml"), "mediahound"),
]

# pywebview loads a platform backend lazily; make sure PyInstaller keeps them.
hiddenimports = collect_submodules("webview") + ["PIL.Image", "qrcode", "requests"]

a = Analysis(
    [os.path.join(SPECPATH, "mediahound_app.py")],   # noqa: F821 - launcher imports the package
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

ICON_WIN = os.path.join(SPECPATH, "mediahound.ico")          # noqa: F821
ICON_MAC = os.path.join(SPECPATH, "mediahound.icns")         # noqa: F821

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="MediaHound", console=False,                        # windowed (no terminal)
    icon=(ICON_WIN if sys.platform == "win32" else None),
)
coll = COLLECT(exe, a.binaries, a.datas, name="MediaHound")

if sys.platform == "darwin":
    app = BUNDLE(
        coll, name="MediaHound.app", icon=ICON_MAC,
        bundle_identifier="com.chirayath.mediahound",
        info_plist={"NSHighResolutionCapable": True, "LSApplicationCategoryType": "public.app-category.utilities"},
    )
