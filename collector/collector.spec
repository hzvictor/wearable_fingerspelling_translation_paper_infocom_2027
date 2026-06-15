# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ASL Fingerspelling Collector.

Build:  pyinstaller collector.spec
Output: dist/ASL Collector.app  (--windowed --onedir)

Critical for a working BLE app on a fresh Mac:
  - pyobjc framework submodules collected (CoreBluetooth/Foundation/objc).
  - NSBluetoothAlwaysUsageDescription in Info.plist (without it macOS TCC
    silently denies BLE -> CBManagerStateUnauthorized).
  - assets + builtin protocol JSON bundled as datas.
NOTE: build on arm64; if pyobjc/PyInstaller misbehave on system Python 3.9,
pin the build venv to Python 3.11/3.12.
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hiddenimports = (
    collect_submodules("CoreBluetooth")
    + collect_submodules("Foundation")
    + ["objc", "libdispatch", "CoreFoundation"]
)

datas = [
    ("assets/asl_reference", "assets/asl_reference"),
    ("protocols/builtin", "protocols/builtin"),
]
# CustomTkinter ships theme JSON + assets that must be bundled, else the frozen
# app crashes at set_default_color_theme.
datas += collect_data_files("customtkinter")

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy"],  # not used; keep bundle small
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="ASLCollector", debug=False, strip=False, upx=False, console=False,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="ASLCollector",
)
app = BUNDLE(
    coll,
    name="ASL Collector.app",
    icon=None,
    bundle_identifier="com.research.aslcollector",
    info_plist={
        "CFBundleName": "ASL Collector",
        "CFBundleDisplayName": "ASL Collector",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSBluetoothAlwaysUsageDescription":
            "Connects to your Tap Strap 2 to record finger-motion data.",
        "NSBluetoothPeripheralUsageDescription":
            "Connects to your Tap Strap 2 to record finger-motion data.",
    },
)
