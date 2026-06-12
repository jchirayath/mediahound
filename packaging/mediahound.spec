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

# Resolve the package version so it can be stamped into the macOS bundle's Info.plist.
_VERSION = "0.0.0"
try:
    with open(os.path.join(PKG, "__init__.py"), encoding="utf-8") as _fh:
        for _line in _fh:
            if _line.startswith("__version__"):
                _VERSION = _line.split("=", 1)[1].strip().strip('"').strip("'")
                break
except OSError:
    pass

# Bundle the web template + example config at the same package-relative paths the code expects
# (cli.py resolves _PKG_DIR / "web" and _PKG_DIR / "config.example.toml" at runtime).
datas = [
    (os.path.join(PKG, "web"), "mediahound/web"),
    (os.path.join(PKG, "config.example.toml"), "mediahound"),
]

# pywebview loads a platform backend lazily; make sure PyInstaller keeps them.
hiddenimports = collect_submodules("webview") + ["PIL.Image", "qrcode", "requests"]
# On macOS use the NATIVE Cocoa/WebKit backend (pyobjc) — small and built into the OS. Make sure
# its modules are bundled so we don't fall back to (and drag in ~175 MB of) Qt. See `excludes`.
if sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa", "objc", "Foundation", "AppKit", "WebKit", "Quartz"]

# Keep Qt OUT of the bundle. Anaconda (and some system Pythons) ship PyQt, which PyInstaller would
# otherwise collect through pywebview's qt backend, ballooning the app from ~30 MB to ~370 MB. We
# don't use Qt — the platform backend is Cocoa/WebKit (macOS) or EdgeChromium (Windows).
_QT = ["PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy", "webview.platforms.qt",
       "webview.platforms.gtk", "webview.platforms.android"]
# Scientific/anaconda libraries MediaHound never uses but PyInstaller drags in from a fat base
# Python (numpy alone pulls ~44 MB of OpenBLAS + libgfortran). Excluding them is safe — the only
# deps are requests, Pillow, qrcode, keyring, pywebview. Saves ~55 MB.
_FAT = ["numpy", "scipy", "pandas", "matplotlib", "IPython", "tcl", "tk", "_tkinter",
        "PIL.ImageTk", "PIL.ImageQt", "test", "lib2to3", "pydoc_data"]

a = Analysis(
    [os.path.join(SPECPATH, "mediahound_app.py")],   # noqa: F821 - launcher imports the package
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", *_QT, *_FAT],
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
        version=_VERSION,
        info_plist={
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "CFBundleShortVersionString": _VERSION,
            "CFBundleVersion": _VERSION,
        },
    )
