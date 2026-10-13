"""Real local Polish text answer; not a Polish microphone/voice validation."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import os
os.chdir(root)
import json
import tempfile
from dataclasses import replace
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from matek.config import Settings
from matek.manager import MatekManager

cfg = replace(Settings.load(), mode="local", cloud_access=False, microphone=False, system_audio=False,
              continuous_screen=False, manual_screenshots=False, persistent_history=False, speech_output=False,
              response_language="pl", max_output_tokens=160)
with tempfile.TemporaryDirectory(prefix="matek-polish-check-") as folder:
    os.environ["LOCALAPPDATA"] = folder
    app = QApplication([])
    manager = MatekManager(cfg, runtime=False)
    report = {"question": "Czym jest epistemologia?", "live_polish_asr_tested": False, "polish_voice_tested": False}
    def done(answer):
        report["answer"] = answer
        app.quit()
    manager.sig_response_done.connect(done)
    manager.sig_error.connect(lambda error: (report.update(error=error), app.quit()))
    QTimer.singleShot(100, lambda: manager.submit_question(report["question"]))
    QTimer.singleShot(60000, app.quit)
    app.exec()
    report["cloud_entries"] = len(manager.ledger.history())
    manager.shutdown()
(root / "artifacts/local-polish.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))
assert report.get("answer") and report["cloud_entries"] == 0
