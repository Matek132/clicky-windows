import importlib.metadata
import shutil
import sys
from pathlib import Path
from .config import Settings, data_dir


def diagnose():
    print("Matek local diagnostics (no capture, audio recording or AI requests)")
    print("Python:", sys.version.split()[0])
    print("Data directory:", data_dir())
    for package in ("PySide6", "mss", "faster-whisper", "PyAudioWPatch", "webrtcvad-wheels", "httpx", "keyring"):
        try:
            print(package, importlib.metadata.version(package))
        except importlib.metadata.PackageNotFoundError:
            print(package, "MISSING")
    cfg = Settings.load()
    print("Offline speech model:", "ready" if (Path(cfg.whisper_model) / "model.bin").exists() else "missing")
    print("Tesseract:", cfg.tesseract_path or shutil.which("tesseract") or "not installed")
    print("Configured mode:", cfg.mode)
    print("Cloud permission:", cfg.cloud_access)
    return 0
