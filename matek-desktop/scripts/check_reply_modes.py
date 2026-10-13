"""Recognized speech -> real Ollama -> silent captions / explicit offline voice."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import os
import tempfile
import time
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from companion.app import Companion
from companion.config import Settings
from companion.context import Transcript

root = Path(__file__).resolve().parent.parent
cfg = replace(Settings.load(), mode="hybrid", cloud_access=False, microphone=True,
              activation="automatic", debounce_seconds=1, speech_output=True,
              continuous_screen=False, manual_screenshots=False, system_audio=False,
              persistent_history=False, max_output_tokens=120)
results, captions, voiced = [], [], []
questions = ["How do I make a lantern in Minecraft?", "Matek, what is two plus two?"]
with tempfile.TemporaryDirectory(prefix="matek-reply-modes-") as directory:
    os.environ["LOCALAPPDATA"] = directory
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with patch("companion.app.AudioService.start", lambda self: None):
        companion = Companion(app, cfg, runtime_hooks=False)
    companion.speech.text_changed.connect(captions.append)
    companion.speech.speaking_changed.connect(lambda value: voiced.append(value) if value else None)
    def begin():
        captions.clear()
        voiced.clear()
        companion.transcript(companion.generation, Transcript(time.time(), questions[len(results)], "microphone", 1))
        # Noise / resumed conversation must not cancel generation.
        companion.activity(companion.generation, "microphone", True)
        companion.activity(companion.generation, "microphone", False)
        assert not companion.cancel.is_set()
    def complete():
        if not companion.overlay.answer or companion.busy:
            return
        results.append({"question": questions[len(results)], "answer": companion.overlay.answer,
                        "caption_updates": len(captions), "voiced": bool(voiced),
                        "cloud_entries": len(companion.ledger.history())})
        if len(results) == 2:
            app.quit()
        else:
            QTimer.singleShot(2200, begin)
    companion.speech.completed.connect(complete)
    # Any credential lookup proves an incorrect cloud routing decision.
    with patch("companion.app.Credentials.get", side_effect=AssertionError("Cloud key lookup forbidden")):
        QTimer.singleShot(200, begin)
        QTimer.singleShot(150000, app.quit)
        app.exec()
    companion.shutdown()
(root / "artifacts" / "reply-modes.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
assert len(results) == 2
assert not results[0]["voiced"] and results[1]["voiced"]
assert all(row["caption_updates"] > 1 and row["cloud_entries"] == 0 for row in results)
