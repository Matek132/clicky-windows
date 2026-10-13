"""Recorded-question → automatic detection → real local answer → offline voice/captions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import os
import tempfile
import time
from dataclasses import replace
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from companion.config import Settings
from companion.context import Transcript
from companion.app import Companion
from companion.ui import STYLE

root = Path(__file__).resolve().parent.parent
recorded = json.loads((root / "artifacts" / "long-question-check.json").read_text())
cfg = replace(Settings.load(), mode="local", cloud_access=False, activation="automatic", microphone=True,
              system_audio=False, manual_screenshots=False, continuous_screen=False,
              persistent_history=False, speech_output=True, verbosity="quick", max_output_tokens=120)
report = {"question": recorded["question"], "no_hotkey": True}
with tempfile.TemporaryDirectory(prefix="matek-handsfree-") as directory:
    os.environ["LOCALAPPDATA"] = directory
    app = QApplication([])
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    # Feed only the deterministic recorded question, never ambient voice into the test.
    from unittest.mock import patch
    with patch("companion.app.AudioService.start", lambda self: None):
        companion = Companion(app, cfg, runtime_hooks=False)
    captions = []
    companion.speech.text_changed.connect(captions.append)
    started = time.monotonic()
    def begin():
        companion.transcript(companion.generation, Transcript(time.time(), recorded["question"], "microphone", confidence=1))
    def complete():
        report.update({"answer": companion.overlay.answer, "words": len(companion.overlay.answer.split()),
                       "caption_updates": len(captions), "voice": companion.speech.tts.voice().name(),
                       "cloud_ledger_entries": len(companion.ledger.history()), "seconds": round(time.monotonic() - started, 2),
                       "echo_guard_active": companion.echo_suppression.is_set()})
        companion.overlay.grab().save(str(root / "artifacts" / "handsfree-answer.png"))
        app.quit()
    companion.speech.completed.connect(complete)
    QTimer.singleShot(300, begin)
    QTimer.singleShot(150000, app.quit)
    app.exec()
    companion.shutdown()
(root / "artifacts" / "handsfree-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
assert report.get("answer") and report["words"] <= 55 and report["caption_updates"] > 3
assert "nuggets" in report["answer"].lower() and "torch" in report["answer"].lower()
assert report["cloud_ledger_entries"] == 0
