# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the portable HeadSize Studio build.

Build it with ``python tools/build_exe.py`` (which renames the output and writes
SHA256SUMS.txt) or directly::

    pyinstaller packaging/headsize.spec --clean --noconfirm

Design notes
------------
* **onefile** so the in-app updater can replace a single file.
* **windowed** (`console=False`): no console window for users; ``--self-test``
  writes its report to ``%APPDATA%/HeadSizeStudio/logs/self-test.txt`` so a
  packaged build can still be verified in CI.
* The YuNet model and the generated icon are bundled as data.
* Unused Qt modules are excluded; they would add tens of megabytes.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT))

from headsize.version import __version__  # noqa: E402

APP_NAME = "HeadSize-Studio"

EXCLUDES = [
    # not used by this app
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "pdb",
    "matplotlib",
    "scipy",
    "pandas",
    "IPython",
    "jupyter",
    "pytest",
    "sqlite3",
    "lib2to3",
    "pytz",
    # Qt modules we never instantiate
    "PyQt6.QtBluetooth",
    "PyQt6.QtCharts",
    "PyQt6.QtDataVisualization",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtNfc",
    "PyQt6.QtOpenGL",
    "PyQt6.QtPdf",
    "PyQt6.QtPdfWidgets",
    "PyQt6.QtPositioning",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtQuick3D",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtRemoteObjects",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtSql",
    "PyQt6.QtStateMachine",
    "PyQt6.QtTest",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtWebChannel",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebSockets",
    "PyQt6.Qt3DCore",
    "PyQt6.Qt3DRender",
    "PyQt6.Qt3DInput",
    "PyQt6.Qt3DLogic",
    "PyQt6.Qt3DAnimation",
    "PyQt6.Qt3DExtras",
]

a = Analysis(  # noqa: F821 - injected by PyInstaller
    [str(ROOT / "headsize" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "headsize" / "assets"), "headsize/assets"),
    ],
    hiddenimports=["PyQt6.QtSvg", "headsize.ui.main_window"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)  # noqa: F821 - injected by PyInstaller

exe = EXE(  # noqa: F821 - injected by PyInstaller
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "headsize" / "assets" / "icons" / "headsize.ico"),
    version=str(ROOT / "packaging" / "version_info.txt")
    if (ROOT / "packaging" / "version_info.txt").is_file()
    else None,
    contents_directory="_internal",
)

ARTIFACT_VERSION = __version__
