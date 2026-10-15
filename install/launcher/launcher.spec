# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Universal Adept Launcher.

Produces a single self-contained executable per platform:

- Windows: ``Adept Launcher.exe`` (windowed bootloader — no console window)
- Linux:   ``adept-launcher``   (headless, no console attachment)
- macOS:   ``Adept UI``         (Mach-O installed as Contents/MacOS/Adept UI)

The bundle carries the ``adept_lifecycle`` package and the brand emblem so the
update engine and its progress page work identically frozen and unfrozen. The
launcher is the single update authority; Electron performs no handoff.
"""

import os
import sys

block_cipher = None

# SPECPATH is the directory containing this spec file (install/launcher).
# Repo root is two levels up.
_SPEC_DIR = os.path.abspath(globals().get("SPECPATH", os.getcwd()))
REPO_ROOT = os.path.abspath(os.path.join(_SPEC_DIR, "..", ".."))
LAUNCHER_DIR = os.path.join(REPO_ROOT, "install", "launcher")
LIFECYCLE_DIR = os.path.join(REPO_ROOT, "install", "lifecycle")
EMBLEM = os.path.join(REPO_ROOT, "studio-web", "public", "brand", "adept-ui-emblem.webp")

pathex = [LAUNCHER_DIR, LIFECYCLE_DIR]

datas = []
if os.path.isfile(EMBLEM):
    datas.append((EMBLEM, "brand"))

# Platform-specific executable naming and console behavior.
is_windows = sys.platform == "win32"
is_macos = sys.platform == "darwin"

if is_windows:
    exe_name = "Adept Launcher"
elif is_macos:
    exe_name = "Adept UI"
else:
    exe_name = "adept-launcher"

# Windows: windowed bootloader (no console). POSIX: console=False is ignored by
# the POSIX bootloader, which is already headless.
console = False

a = Analysis(
    [os.path.join(LAUNCHER_DIR, "launcher_main.py")],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=[
        "adept_lifecycle",
        "adept_lifecycle.cli",
        "adept_lifecycle.manager",
        "adept_lifecycle.release",
        "adept_lifecycle.registry",
        "adept_lifecycle.detect",
        "adept_lifecycle.desktop",
        "adept_lifecycle.layout",
        "adept_lifecycle.safety",
        "adept_lifecycle.trust",
        "adept_launcher",
        "adept_launcher.launcher",
        "adept_launcher._paths",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
