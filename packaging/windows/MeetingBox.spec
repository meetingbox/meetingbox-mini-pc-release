# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the MeetingBox Windows desktop port.

Builds TWO one-dir executables that share a single ``_internal`` payload:

  * ``MeetingBox.exe``        – the Kivy UI (entry: device-ui/src/main.py)
  * ``meetingbox-audio.exe``  – the audio capture child (entry: audio/audio_capture.py)

The UI's ``audio_supervisor`` launches ``meetingbox-audio.exe`` as a sibling
process (it cannot run ``audio_capture.py`` as a script once frozen, because
``sys.executable`` is the UI binary).

Run from the repo root:

    device-ui\\.venv\\Scripts\\pyinstaller.exe --noconfirm packaging\\windows\\MeetingBox.spec
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)
from kivy_deps import sdl2, glew, angle

# ``SPECPATH`` is injected by PyInstaller at runtime.
REPO_ROOT = Path(SPECPATH).resolve().parent.parent  # packaging/windows -> repo root
DEVICE_UI = REPO_ROOT / "device-ui"
SRC = DEVICE_UI / "src"
AUDIO = REPO_ROOT / "audio"

# ---------------------------------------------------------------------------
# Shared data files (land under _internal/, i.e. sys._MEIPASS at runtime).
# ---------------------------------------------------------------------------
datas = []
datas += [(str(DEVICE_UI / "assets"), "assets")]
if (AUDIO / "config.yaml").is_file():
    datas += [(str(AUDIO / "config.yaml"), ".")]

# Bundle a default desktop env next to the exe payload as a fallback.
_env_template = REPO_ROOT / "packaging" / "windows" / "device-ui.env"
if _env_template.is_file():
    datas += [(str(_env_template), ".")]

# Third-party packages that ship data / need full collection.
binaries = []
hiddenimports = []
for pkg in ("vosk", "sounddevice", "_cffi_backend", "cffi"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# certifi CA bundle (httpx / websockets TLS).
try:
    datas += collect_data_files("certifi")
except Exception:
    pass

# ---------------------------------------------------------------------------
# Hidden imports — our own packages plus dynamically imported deps.
# ---------------------------------------------------------------------------
hiddenimports += collect_submodules("screens")
hiddenimports += collect_submodules("components")
hiddenimports += [
    "single_instance",
    "env_file",
    "net_status",
    "tts_windows",
    "audio_output",
    "kivy.core.window.window_sdl2",
    "kivy.core.text.text_sdl2",
    "kivy.core.image.img_sdl2",
    "kivy.core.audio.audio_sdl2",
    "kivy.core.clipboard.clipboard_sdl2",
    "pyttsx3",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "comtypes",
    "comtypes.client",
    "comtypes.stream",
    "win32com",
    "win32com.client",
    "sounddevice",
    "soundfile",
    "vosk",
    "numpy",
    "yaml",
    "httpx",
    "websockets",
    "qrcode",
    "PIL",
    "PIL.Image",
]

# webrtcvad is optional on Windows (capture forces the sounddevice backend and
# guards self.vad). The stock pyinstaller-hooks-contrib hook for ``webrtcvad``
# is incompatible with the ``webrtcvad-wheels`` build, so exclude it entirely.
VAD_EXCLUDES = ["webrtcvad", "webrtcvad_wheels"]

block_cipher = None

PATHEX = [str(SRC), str(AUDIO), str(REPO_ROOT)]

# ---------------------------------------------------------------------------
# UI analysis
# ---------------------------------------------------------------------------
ui_a = Analysis(
    [str(SRC / "main.py")],
    pathex=PATHEX,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"] + VAD_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Audio child analysis
# ---------------------------------------------------------------------------
audio_hidden = [
    "pyaudio",
    "sounddevice",
    "numpy",
    "yaml",
    "redis",
    "httpx",
    "requests",
    "scipy",
    "scipy.signal",
]

audio_a = Analysis(
    [str(AUDIO / "audio_capture.py")],
    pathex=PATHEX,
    binaries=[],
    datas=[(str(AUDIO / "config.yaml"), ".")] if (AUDIO / "config.yaml").is_file() else [],
    hiddenimports=audio_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "kivy"] + VAD_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

MERGE((ui_a, "MeetingBox", "MeetingBox"), (audio_a, "meetingbox-audio", "meetingbox-audio"))

ui_pyz = PYZ(ui_a.pure, ui_a.zipped_data, cipher=block_cipher)
audio_pyz = PYZ(audio_a.pure, audio_a.zipped_data, cipher=block_cipher)

_icon = REPO_ROOT / "packaging" / "windows" / "meetingbox.ico"
icon_arg = str(_icon) if _icon.is_file() else None

ui_exe = EXE(
    ui_pyz,
    ui_a.scripts,
    [],
    exclude_binaries=True,
    name="MeetingBox",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=icon_arg,
)

audio_exe = EXE(
    audio_pyz,
    audio_a.scripts,
    [],
    exclude_binaries=True,
    name="meetingbox-audio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    icon=icon_arg,
)

coll = COLLECT(
    ui_exe,
    ui_a.binaries,
    ui_a.zipfiles,
    ui_a.datas,
    audio_exe,
    audio_a.binaries,
    audio_a.zipfiles,
    audio_a.datas,
    *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins + angle.dep_bins)],
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MeetingBox",
)
