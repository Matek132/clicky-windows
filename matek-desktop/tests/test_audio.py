from pathlib import Path
import wave
import numpy as np
import pytest
from companion.audio import SpeechSegmenter, Transcriber
from companion.config import Settings
from companion.detection import QuestionDetector


def test_silence_produces_no_segment():
    vad = SpeechSegmenter()
    silence = b"\0" * 960
    for _ in range(1000):
        assert vad.feed(silence) is None
    assert len(vad.pre) <= 10
    assert not vad.frames


def test_vad_segmentation_is_bounded():
    segmenter = SpeechSegmenter()
    class Speech:
        def is_speech(self, *args):
            return True
    segmenter.vad = Speech()
    results = []
    for _ in range(1100):
        result = segmenter.feed(b"\1" * 960)
        if result:
            results.append(result)
    assert results
    assert all(len(pcm) <= 500 * 960 for pcm in results)


def test_recorded_question_offline(monkeypatch):
    fixture = Path("tests/fixtures/question.wav")
    model = Path("models/whisper-tiny.en/model.bin")
    if not fixture.exists() or not model.exists():
        pytest.skip("Run scripts/download_model.py and scripts/make_audio_fixture.ps1 for real offline speech integration")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    # Forbid Python socket connections during inference.
    import socket
    def blocked(*args, **kwargs):
        raise AssertionError("Offline inference attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    with wave.open(str(fixture), "rb") as recording:
        assert recording.getframerate() == 16000
        assert recording.getnchannels() == 1
        pcm = recording.readframes(recording.getnframes())
    transcriber = Transcriber(Settings())
    result = transcriber.transcribe(pcm, "microphone")
    assert "what" in result.text.lower()
    assert "mean" in result.text.lower()
    detector = QuestionDetector(Settings(activation="automatic", confidence=0.2))
    assert detector.detect(result.text, result.source, result.confidence)
