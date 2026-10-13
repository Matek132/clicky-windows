"""Recorded local ASR -> Clicky orchestration -> real Ollama -> native offline TTS."""
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import json
import os
import tempfile
import time
import wave
from dataclasses import replace
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from matek.config import Settings
from matek.audio import Transcriber
from matek.manager import MatekManager
from matek.panel import MatekPanel

cfg = replace(Settings.load(), mode="local", cloud_access=False, persistent_history=False, speech_policy="full", local_model="qwen2.5vl:3b",
              microphone=True, system_audio=False, continuous_screen=False, manual_screenshots=False,
              activation="automatic", language="", whisper_model=str(root / "models/whisper-base"),
              max_output_tokens=160, speech_output=True, confidence=.4)
with wave.open(str(root.parent / "tests/fixtures/question.wav"), "rb") as audio:
    pcm = audio.readframes(audio.getnframes())
recognized = Transcriber(cfg).transcribe(pcm, "microphone")
report = {"recognized_fixture": recognized.text, "confidence": recognized.confidence}
with tempfile.TemporaryDirectory(prefix="matek-clicky-native-") as directory:
    os.environ["LOCALAPPDATA"] = directory
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    manager = MatekManager(cfg, runtime=False)
    panel = MatekPanel(manager)
    manager.sig_response_chunk.connect(panel.append_response_chunk)
    manager.sig_state_changed.connect(panel.set_state)
    manager.sig_error.connect(lambda error: report.update(error=error))
    captions = []
    manager.caption.connect(captions.append)
    started = time.monotonic()
    def begin():
        # Real ASR is checked above; use a general question for inference without personal desktop capture.
        manager._transcript(manager.generation, type(recognized)(time.time(), "What is the meaning of epistemology?", "microphone", 1))
    def completed():
        if not panel._full_answer:
            return
        report.update(answer=panel._full_answer, caption_updates=len(captions),
                      voice=manager.speech.tts.voice().name(), frontend=type(panel).__mro__[1].__name__,
                      cloud_entries=len(manager.ledger.history()), seconds=round(time.monotonic()-started,2))
        panel.grab().save(str(root.parent / "artifacts/clicky-matek-answer.png"))
        app.quit()
    manager.speech.completed.connect(completed)
    QTimer.singleShot(200, begin)
    QTimer.singleShot(150000, app.quit)
    app.exec()
    manager.shutdown()
report_path = root.parent / "artifacts/clicky-matek-native.json"
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
assert "what" in report["recognized_fixture"].lower() and report.get("answer")
assert report["caption_updates"] > 2 and report["cloud_entries"] == 0 and "knowledge" in report["answer"].lower()
