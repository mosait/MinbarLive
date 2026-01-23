# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

ICON_PATH = "public/MinbarLive.ico"

hiddenimports = (
    collect_submodules("sounddevice")
    + collect_submodules("numpy")
    + collect_submodules("scipy")
    + collect_submodules("openai")
    + collect_submodules("dotenv")
    + collect_submodules("screeninfo")
    + collect_submodules("keyring")
)

# Exclude the MASSIVE unused libraries
excludes = [
    "torch",
    "torchvision", 
    "torchaudio",
    "tensorflow",
    "keras",
    "dask",
    "pygments",
    "pytest",
    "ruff",
    "matplotlib",
    "PIL",
    "pandas",
    "IPython",
    "notebook",
    "jupyter",
    "tkinter.test",
]

# Collect native binaries (DLLs) required by these packages.
binaries = (
    collect_dynamic_libs("sounddevice")
    + collect_dynamic_libs("numpy")
    + collect_dynamic_libs("scipy")
)

# Bundle project data/ and public/ into the executable (available under sys._MEIPASS/)
datas = [("data", "data"), ("public", "public")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# One-file mode - slower startup but easier distribution
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MinbarLive",
    icon=ICON_PATH,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
