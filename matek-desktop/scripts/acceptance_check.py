"""A real, free, local screen-question round trip through the Qt application."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import os
import tempfile
import time
from dataclasses import replace
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt, QTimer
from companion.config import Settings
from companion.app import Companion
from companion.ui import STYLE


ROOT = Path(__file__).resolve().parent.parent
cfg = replace(Settings.load(), mode="local", cloud_access=False, microphone=False, system_audio=False,
              continuous_screen=False, manual_screenshots=True, persistent_history=False,
              local_model="qwen2.5vl:3b", local_vision=True, max_output_tokens=180)
report = {"cloud_requests": 0, "model": cfg.local_model}
with tempfile.TemporaryDirectory(prefix="matek-acceptance-") as directory:
    os.environ["LOCALAPPDATA"] = directory
    app = QApplication([])
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    card = QLabel("MATEK SOFTWARE TEST\n\nERROR CS1002\n\nint value = 2 + 2\n\nExpected: ;")
    card.setWindowTitle("Matek Acceptance Test")
    card.setAlignment(Qt.AlignCenter)
    card.setStyleSheet("background:white;color:black;font:64px 'Segoe UI';")
    card.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    card.setGeometry(app.screens()[0].geometry())
    card.showFullScreen()
    card.raise_()
    companion = Companion(app, cfg, runtime_hooks=False)
    started = [0]
    asked = [False]
    phase = [0]
    def ask():
        started[0] = time.monotonic()
        asked[0] = True
        companion.ask("Read the error code on the screen. Explain its meaning in C# and how to fix it in two sentences.")
    def inspect():
        if asked[0] and not companion.busy:
            result = {"answer": companion.overlay.answer, "status": companion.overlay.status.text(),
                           "seconds": round(time.monotonic() - started[0], 2),
                           "screenshot_frames": len(companion.engine.frames),
                           "cloud_ledger_entries": len(companion.ledger.history()),
                           "error_code_in_answer": "CS1002" in companion.overlay.answer,
                           "fix_in_answer": "semicolon" in companion.overlay.answer.lower(),
                           "corrected_declaration": "int value = 2 + 2;" in companion.overlay.answer}
            if phase[0] == 0:
                report.update(result)
                phase[0] = 1
                started[0] = time.monotonic()
                companion.ask("Show the corrected C# variable declaration from the screen, including the missing semicolon.")
                return
            report["followup"] = result
            companion.overlay.grab().save(str(ROOT / "artifacts" / "live-answer.png"))
            app.quit()
    timer = QTimer()
    timer.timeout.connect(inspect)
    timer.start(100)
    QTimer.singleShot(1500, ask)
    QTimer.singleShot(180000, app.quit)
    app.exec()
    if "answer" not in report:
        report["error"] = "Timed out"
    (ROOT / "artifacts" / "acceptance-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
