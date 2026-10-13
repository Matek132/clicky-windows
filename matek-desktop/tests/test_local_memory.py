from dataclasses import replace
from datetime import datetime, timezone
import time
from companion.config import Settings
from companion.context import Package, Frame, Transcript
from companion.memory import CompanionMemory
from companion.audio import AudioService


def package(question):
    now = time.time()
    return Package(question, now, "typed", (Frame(now - 5, b"image", "Editor", "Code"),),
                   (Transcript(now - 5, "A lecturer said this", "system"),), (), "")


def test_general_question_excludes_capture_and_never_queries_memory():
    memory = CompanionMemory(Settings(memory_backend="screenpipe", system_audio=True, continuous_screen=True))
    def forbidden(*args):
        raise AssertionError("General question must not query recording history")
    memory.client.request = forbidden
    result = memory.select(package("What is gravity?"))
    assert not result.frames and not result.transcripts


def test_historical_question_cannot_use_recent_ram_as_old_evidence():
    memory = CompanionMemory(Settings(continuous_screen=True))
    result = memory.select(package("What happened on screen three days ago?"))
    # Numeric dates are supported; unsupported wording must not pretend to parse it.
    result = memory.select(package("What happened on screen 3 days ago?"))
    assert not result.frames and "older events are unavailable" in result.notes


def test_capture_ownership_requires_fresh_per_source_health():
    memory = CompanionMemory(Settings(memory_backend="screenpipe"))
    fresh = datetime.now(timezone.utc).isoformat()
    memory.update_health({"frame_status": "ok", "last_frame_timestamp": fresh,
                          "audio_status": "disabled", "last_audio_timestamp": fresh})
    assert memory.owns("screen") and not memory.owns("system")
    assert not memory.owns("microphone")
    memory.update_health({"frame_status": "ok", "last_frame_timestamp": "2020-01-01T00:00:00Z"})
    assert not memory.owns("screen")
    memory.close()
    assert not memory.owns("screen")


def test_external_audio_owner_prevents_opening_duplicate_capture(monkeypatch):
    service = AudioService(Settings(), lambda value: None, lambda value: None)
    def owns(source):
        assert source == "system"
        service.stop.set()
        return True
    service.source_owned = owns
    def forbidden():
        raise AssertionError("Our audio stream must stay closed while external recorder owns it")
    monkeypatch.setattr("companion.audio.audio_manager", forbidden)
    service._capture("system")
