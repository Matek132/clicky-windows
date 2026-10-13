"""Exercise Clicky's real question pipeline with deterministic provider substitutes."""
import asyncio
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace
import pytest
from PyQt6.QtWidgets import QApplication
from memory_backend import Evidence, MemoryResult
import companion_manager as module


@pytest.mark.parametrize("question,history,expected_images", [
    ("What is gravity?", MemoryResult("none"), []),
    ("What happened on screen an hour ago?", MemoryResult("screenpipe", (Evidence(1000, "screen", "a compiler error", image="historical-image"),)), ["historical-image"]),
])
def test_existing_voice_pipeline_uses_selected_memory(monkeypatch, tmp_path, question, history, expected_images):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(module.CompanionManager, "_run_loop", lambda self: None)
    monkeypatch.setattr(module, "active_window_title", lambda: "Editor")
    def forbidden_capture():
        raise AssertionError("General and historical questions must not capture current screen")
    monkeypatch.setattr(module, "capture_all_screens", forbidden_capture)
    manager = module.CompanionManager()
    manager._web_search_enabled = manager._journal_enabled = manager._multilang = manager._ocr_enabled = False
    manager._listener = SimpleNamespace(stop_recording=lambda: b"\0" * 32000, stop=lambda: None)
    manager._memory.retrieve = lambda text: history
    async def transcribe(pcm):
        return question
    calls, voices, errors = [], [], []
    class LLM:
        async def stream_response(self, **kwargs):
            calls.append(kwargs)
            yield "A short answer."
    async def speak(text):
        voices.append(text)
    manager._get_stt = lambda: SimpleNamespace(transcribe=transcribe)
    manager._get_llm = lambda: LLM()
    manager._get_tts = lambda: SimpleNamespace(speak=speak)
    manager.sig_error.connect(errors.append)
    asyncio.run(manager._end_capture_and_process())
    assert not errors
    assert len(calls) == 1 and calls[0]["screenshots_b64"] == expected_images
    assert voices == ["A short answer."]
    if history.records:
        assert "compiler error" in calls[0]["system_prompt"]
    manager.shutdown()
