# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the desktop app (ASCII only on purpose).

Do NOT hardcode local paths here. The previous version embedded a Conda
install directory and one developer's project directory, which breaks on
any other machine and leaks a personal directory layout into the package.
Everything below is derived from SPECPATH and the current interpreter.
"""

import os
import sysconfig

block_cipher = None

# site-packages of the interpreter running PyInstaller (never hardcoded)
_SITE_PACKAGES = sysconfig.get_paths()["purelib"]
vtk_path = os.path.join(_SITE_PACKAGES, "vtkmodules")

# SPECPATH is injected by PyInstaller: the directory holding this spec (suFabUI/)
_UI_SRC = os.path.join(SPECPATH, "src")
_ENGINE_SRC = os.path.join(SPECPATH, os.pardir, "suFabEngine", "src")

a = Analysis(
    [os.path.join(_UI_SRC, "suFabUI", "main.py")],
    pathex=[_UI_SRC, _ENGINE_SRC],
    binaries=[
        (os.path.join(vtk_path, "*.pyd"), "."),   # VTK python extension modules
        (os.path.join(vtk_path, "*.dll"), "."),   # VTK dependent dlls, if any
    ],
    datas=[
        (os.path.join(_UI_SRC, "suFabUI", "ui"), "suFabUI/ui"),
        (vtk_path, "vtkmodules"),
    ],
    hiddenimports=[
        "suFabEngine",
        "vtkmodules.vtkCommonCore",
        "vtkmodules.vtkCommonTransforms",
        "vtkmodules.vtkCommonMath",
        "vtkmodules.vtkCommonDataModel",
        "vtkmodules.vtkRenderingCore",
        "vtkmodules.vtkRenderingOpenGL2",
        "vtkmodules.qt.QVTKRenderWindowInteractor",
        "vtkmodules.all",
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
    name="suFabUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="suFabUI",
)
