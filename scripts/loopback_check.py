"""Play generated fixture through default output; verify actual offline WASAPI ASR."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import os
os.chdir(root)
from dataclasses import replace
import json
import tempfile
import time
import wave
import numpy as np
import sounddevice
from matek.config import Settings
from matek.audio import AudioService

cfg = replace(Settings.load(), microphone=False, system_audio=True, system_questions=False,
              language="en", whisper_model=str(root / "models/whisper-base"))
snippets, statuses = [], []
audio = AudioService(cfg, snippets.append, statuses.append)
with wave.open(str(root / "tests/fixtures/question.wav"), "rb") as fixture:
    samples = np.frombuffer(fixture.readframes(fixture.getnframes()), dtype=np.int16).astype(np.float32)/32768
audio.start()
try:
    time.sleep(1)
    sounddevice.play(samples, 16000)
    sounddevice.wait()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not any("epistemology" in row.text.lower() for row in snippets):
        time.sleep(.1)
    matches = [row for row in snippets if "epistemology" in row.text.lower()]
    report = {"loopback_fixture_recognized": bool(matches), "source": matches[0].source if matches else None,
              "confidence": matches[0].confidence if matches else None,
              "transcriptions": audio.transcriptions, "raw_recordings_saved": False,
              "input_errors": [s for s in statuses if "unavailable" in s]}
finally:
    audio.close()
(root / "artifacts").mkdir(exist_ok=True)
(root / "artifacts/loopback.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
assert report["loopback_fixture_recognized"], "Inspect default playback/loopback device selection"
