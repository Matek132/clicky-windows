"""Master prompt acceptance: actual Clicky subclass, deterministic local providers."""
import asyncio
import base64
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
import os
import time
from types import SimpleNamespace
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PIL import Image
from PyQt6.QtWidgets import QApplication
from ai.base_provider import Message
from companion_manager import CompanionManager
from matek.config import Settings
from matek.context import Frame, Transcript
from matek.gateway import GuardedProvider
from matek.manager import MatekManager
from matek.panel import MatekPanel
from matek.routing import ReasoningRouter, classify


def pump(app, condition, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not condition():
        app.processEvents()
        time.sleep(.01)
    assert condition(), "Clicky/Matek operation timed out"


class Provider:
    def __init__(self):
        self.calls = []
        self.last_usage = None
    async def stream_response(self, **kwargs):
        self.calls.append(kwargs)
        yield "A short answer."
    async def health_check(self):
        return True
    async def close(self):
        pass


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    settings = Settings(microphone=True, system_audio=True, continuous_screen=True, activation="automatic", local_vision=True,
                        speech_output=False, max_output_tokens=160, confidence=.4)
    manager = MatekManager(settings, runtime=False)
    provider = Provider()
    manager._providers["ollama"] = GuardedProvider(manager, provider, "ollama")
    manager._providers["openai"] = GuardedProvider(manager, provider, "openai")
    yield app, manager, provider
    manager.shutdown()
    app.processEvents()


def ask(app, manager, question):
    future = asyncio.run_coroutine_threadsafe(manager.ask(question), manager._loop)
    pump(app, future.done)
    future.result()


def jpeg(colour):
    out = BytesIO()
    Image.new("RGB", (64, 64), colour).save(out, "JPEG")
    return out.getvalue()


def test_1_general_knowledge_uses_clicky_pipeline_without_screenshot(runtime, monkeypatch):
    app, manager, provider = runtime
    assert isinstance(manager, CompanionManager)
    monkeypatch.setattr(manager, "_capture_screens", lambda: pytest.fail("Unexpected capture"))
    ask(app, manager, "What is the meaning of epistemology?")
    assert len(provider.calls) == 1 and not provider.calls[0]["screenshots_b64"]
    assert "any subject" in provider.calls[0]["system_prompt"]
    assert manager._last_response == "A short answer."


def test_2_screen_question_includes_fresh_frame(runtime, monkeypatch):
    app, manager, provider = runtime
    calls = []
    encoded = base64.b64encode(jpeg("red")).decode()
    def capture():
        calls.append(True)
        return [SimpleNamespace(base64_jpeg=encoded)]
    monkeypatch.setattr(manager, "_capture_screens", capture)
    ask(app, manager, "What does that symbol mean?")
    assert calls and provider.calls[0]["screenshots_b64"] == [encoded]


def test_3_previous_event_selects_before_and_after(runtime, monkeypatch):
    app, manager, provider = runtime
    now = time.time()
    before, after = jpeg("red"), jpeg("blue")
    manager._memory.engine.add_frame(Frame(now - 10, before, "game", "Minecraft", change=.01))
    manager._memory.engine.add_frame(Frame(now - 5, after, "game", "Minecraft", change=.9))
    monkeypatch.setattr(manager, "_capture_screens", lambda: [SimpleNamespace(base64_jpeg=base64.b64encode(after).decode())])
    ask(app, manager, "What happened to that?")
    assert len(provider.calls[0]["screenshots_b64"]) == 2
    assert "sparse samples" in provider.calls[0]["system_prompt"]


def test_4_followup_preserves_conversation_without_capture(runtime, monkeypatch):
    app, manager, provider = runtime
    monkeypatch.setattr(manager, "_capture_screens", lambda: pytest.fail("Unexpected capture"))
    ask(app, manager, "What is artificial consciousness?")
    ask(app, manager, "How would that differ from human consciousness?")
    assert any(item.content == "What is artificial consciousness?" for item in provider.calls[-1]["history"])
    assert not provider.calls[-1]["screenshots_b64"]


def test_5_lecture_uses_local_system_transcript(runtime):
    app, manager, provider = runtime
    manager._memory.engine.add_transcript(Transcript(time.time(), "Epistemology is the study of knowledge.", "system"))
    ask(app, manager, "What did the lecturer mean?")
    assert "study of knowledge" in provider.calls[0]["system_prompt"]


def test_6_idle_never_dispatches_provider(runtime):
    app, manager, provider = runtime
    for _ in range(100):
        manager._memory.engine.add_transcript(Transcript(time.time(), "Background lecture content", "system"))
        app.processEvents()
    assert not provider.calls and not manager.ledger.history()


def test_7_router_never_escalates_without_permission(runtime):
    _, manager, _ = runtime
    router = ReasoningRouter()
    cfg = replace(manager.settings, mode="hybrid", cloud_access=True, escalation="ask")
    assert router.select("What is gravity?", cfg).provider == "ollama"
    assert router.select("Analyse this advanced algorithm in depth", cfg).provider == "openai"
    assert router.select("Analyse this advanced algorithm in depth", cfg).confirm
    assert router.select("Analyse this advanced algorithm in depth", replace(cfg, cloud_access=False)).provider == "ollama"


def test_8_spoken_stop_cancels_without_provider_call(runtime):
    app, manager, provider = runtime
    manager.echo.set()
    manager._transcript(manager.generation, Transcript(time.time(), "Stop.", "microphone"))
    app.processEvents()
    assert manager._cancel_flag and not provider.calls


def test_9_gaming_has_bounded_context_and_cpu_inference(runtime):
    _, manager, _ = runtime
    manager.settings.preset = "gaming"
    manager._configure_providers()
    from config import cfg
    assert cfg.ollama_num_gpu == 0 and cfg.ollama_keep_alive == "0"
    assert manager._memory.observer.delay() >= 10
    for _ in range(100):
        manager._memory.engine.add_frame(Frame(time.time(), jpeg("blue"), "game", "game"))
    assert manager._memory.engine.inspect()["frames"] <= manager.settings.max_frames


def test_10_privacy_filters_excluded_capture_and_context(runtime):
    _, manager, _ = runtime
    manager._memory.engine.add_frame(Frame(time.time(), b"secret", "Bitwarden", "vault"))
    assert manager._memory.engine.inspect()["frames"] == 0


def test_cloud_decline_does_not_reserve_or_dispatch(runtime):
    app, manager, provider = runtime
    manager.settings.mode = "cloud"
    manager.settings.cloud_access = True
    async def decline(*args):
        return False
    manager.confirm_cloud = decline
    ask(app, manager, "What is philosophy?")
    assert not provider.calls and not manager.ledger.history()


def test_cloud_approved_is_accounted_and_budget_blocks_next(runtime):
    app, manager, provider = runtime
    manager.settings.mode = "cloud"
    manager.settings.cloud_access = True
    async def approve(*args):
        return True
    manager.confirm_cloud = approve
    ask(app, manager, "What is mathematics?")
    assert len(provider.calls) == 1 and manager.ledger.history()[0][4] == "completed/estimated"
    manager.settings.daily_usd = 0
    ask(app, manager, "What is chemistry?")
    assert len(provider.calls) == 1


def test_pyqt_clicky_panel_supports_typing_settings_and_history(runtime):
    app, manager, _ = runtime
    panel = MatekPanel(manager)
    panel.show()
    panel.expand()
    assert panel.entry.isVisible() and panel.manager is manager
    panel.hide()
    panel.collapse_timer.stop()
