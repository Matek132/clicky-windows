from dataclasses import replace
from companion.audio import SpeechSegmenter, join_transcript
from companion.audio import mono_input
import numpy as np
from companion.config import Settings
from companion.context import Transcript, ContextEngine
from companion.speech import plain_speech, utf16_prefix
from companion.detection import QuestionDetector


class VAD:
    def is_speech(self, pcm, rate):
        return pcm[0] == 1


def segmenter():
    item = SpeechSegmenter(end_pause=4)
    item.vad = VAD()
    return item


def test_two_second_thinking_pause_does_not_end_question():
    item = segmenter()
    for _ in range(30):
        assert item.feed(b"\1" * 960) is None
    for _ in range(67):
        assert item.feed(b"\0" * 960) is None
    for _ in range(30):
        assert item.feed(b"\1" * 960) is None
    results = [item.feed(b"\0" * 960) for _ in range(134)]
    assert sum(result is not None for result in results) == 1
    assert item.is_final and not item.active


def test_long_question_chunks_are_not_final():
    item = segmenter()
    chunks = []
    for _ in range(1100):
        data = item.feed(b"\1" * 960)
        if data:
            chunks.append((data, item.is_final))
    assert len(chunks) >= 2
    assert all(not final for _, final in chunks)
    assert all(len(data) <= 500 * 960 for data, _ in chunks)
    for _ in range(134):
        item.feed(b"\0" * 960)
    assert item.is_final


def test_overlap_is_joined_without_repeating_words():
    assert join_transcript("How do I build a", "build a lantern in Minecraft?") == "How do I build a lantern in Minecraft?"


def test_partial_context_is_replaced():
    engine = ContextEngine(Settings(system_audio=True), lambda: 1000)
    engine.add_transcript(Transcript(990, "First part", "system", is_final=False, session=5))
    engine.add_transcript(Transcript(995, "First part and second part", "system", session=5))
    assert len(engine.transcripts) == 1


def test_speech_cleanup_and_utf16_progress():
    assert plain_speech("**Use** `eight nuggets`.") == "Use eight nuggets."
    assert utf16_prefix("Hi 😀 there", 5) == "Hi 😀"


def test_unfinished_phrasing_waits_for_continuation():
    assert QuestionDetector.incomplete("How do I?")
    assert QuestionDetector.incomplete("How do I craft")
    assert not QuestionDetector.incomplete("How do I craft a lantern?")
    assert not QuestionDetector.incomplete("Who are you?")
    assert not QuestionDetector.incomplete("What should I do?")
    assert not QuestionDetector.incomplete("What is this used for?")


def test_stereo_microphone_does_not_cancel_or_attenuate():
    stereo = np.array([[1000, -1000], [2000, -2000]], dtype=np.int16)
    assert np.array_equal(mono_input(stereo.tobytes(), 2, "microphone"), [1000, 2000])
    assert np.array_equal(mono_input(stereo.tobytes(), 2, "system"), [0, 0])


def test_conversational_question_and_explicit_voice_request():
    cfg = Settings(activation="automatic", debounce_seconds=1)
    detector = QuestionDetector(cfg, lambda: 100)
    assert detector.detect("Um, how do I make a lantern?", "microphone") == "how do I make a lantern?"
    assert not detector.addressed("How do I make a lantern?")
    assert detector.addressed("Matek, how do I make a lantern?")
    assert detector.addressed("Hey Matech, explain this")
    assert not detector.addressed("Assistant, explain this")
