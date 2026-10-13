"""Speak a known test recipe with Windows' offline voice and verify word callbacks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from companion.config import Settings
from companion.speech import SpokenAnswer

app = QApplication([])
answer = SpokenAnswer(Settings())
words, errors, states = [], [], []
answer.text_changed.connect(words.append)
answer.error.connect(errors.append)
answer.speaking_changed.connect(states.append)
answer.completed.connect(app.quit)
started = time.monotonic()
text = "Put one torch in the centre. Surround it with eight iron nuggets."
def begin():
    answer.feed(text)
    answer.finish()
QTimer.singleShot(100, begin)
QTimer.singleShot(20000, app.quit)
app.exec()
report = {"seconds": round(time.monotonic() - started, 2), "caption_updates": len(words),
          "full_caption": words[-1] if words else "", "speaking_events": states, "errors": errors,
          "voice": answer.tts.voice().name() if answer.tts else None}
Path("artifacts/speech-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
assert words and words[-1] == text and not errors and True in states
