"""Real Whisper/VAD test with a two-second internal pause, using generated speech only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import wave
from companion.audio import SpeechSegmenter, Transcriber
from companion.config import Settings

root = Path(__file__).resolve().parent.parent
def load(name):
    with wave.open(str(root / "artifacts" / name), "rb") as audio:
        assert audio.getframerate() == 16000 and audio.getnchannels() == 1
        return audio.readframes(audio.getnframes())
first, second = load("speech-first.wav"), load("speech-second.wav")
pcm = first + b"\0" * (16000 * 2 * 2) + second + b"\0" * (16000 * 2 * 5)
item = SpeechSegmenter(end_pause=4)
events = []
for at in range(0, len(pcm) - 960, 960):
    chunk = item.feed(pcm[at:at + 960])
    if chunk:
        events.append((chunk, item.is_final))
assert len(events) == 1 and events[0][1], f"Unexpected final-question events: {len(events)}"
question = Transcriber(Settings()).transcribe(events[0][0], "microphone")
report = {"final_question_events": len(events), "internal_pause_seconds": 2,
          "question": question.text, "contains_lantern": "lantern" in question.text.lower()}
(root / "artifacts" / "long-question-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
assert report["contains_lantern"]
