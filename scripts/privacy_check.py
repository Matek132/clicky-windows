"""Real Windows exclusion check using own synthetic sensitive window; no saved pixels."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import os
os.chdir(root)
import json
import tempfile
from dataclasses import replace
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import QTimer, Qt
from matek.config import Settings
from matek.manager import MatekManager

cfg = replace(Settings.load(), mode="local", cloud_access=False, microphone=False, system_audio=False,
              continuous_screen=True, manual_screenshots=True, persistent_history=False, speech_output=False)
with tempfile.TemporaryDirectory(prefix="matek-privacy-check-") as folder:
    os.environ["LOCALAPPDATA"] = folder
    app = QApplication([])
    manager = MatekManager(cfg, runtime=False)
    window = QLabel("SYNTHETIC PRIVATE TEST CONTENT")
    window.setWindowTitle("Bitwarden synthetic privacy test")
    window.setStyleSheet("background:#441122;color:white;font-size:42px;")
    window.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    window.showFullScreen()
    report = {}
    def excluded():
        report["excluded_capture_count"] = len(manager._capture_screens())
        report["excluded_ram_frames"] = manager._memory.engine.inspect()["frames"]
        window.setText("SAFE SYNTHETIC TEST CONTENT")
        window.setWindowTitle("Matek permitted synthetic capture")
        QTimer.singleShot(300, permitted)
    def permitted():
        report["permitted_capture_count"] = len(manager._capture_screens())
        report["cloud_entries"] = len(manager.ledger.history())
        report["pixels_saved"] = False
        app.quit()
    QTimer.singleShot(300, excluded)
    QTimer.singleShot(10000, app.quit)
    app.exec()
    manager.shutdown()
(root / "artifacts/privacy-native.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
assert report["excluded_capture_count"] == 0 and report["excluded_ram_frames"] == 0 and report["permitted_capture_count"] == 1
