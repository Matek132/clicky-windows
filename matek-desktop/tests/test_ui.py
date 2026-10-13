import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import time
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication, QDialog
from companion.config import Settings
from companion.app import Companion
from companion.costs import CostLedger
from companion.security import Credentials
from companion.ui import Overlay, SettingsDialog, GROUPS


@pytest.fixture(scope="module")
def qt():
    return QApplication.instance() or QApplication([])


def pump(qt, predicate, timeout=5):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        qt.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("UI operation timed out")


def test_settings_fields_and_overlay_render(qt, tmp_path):
    overlay = Overlay(Settings())
    overlay.show()
    overlay.append("## Answer\n\nA **formatted** answer.\n\n```python\nprint('hello')\n```")
    qt.processEvents()
    assert "formatted" in overlay.browser.toPlainText()
    assert overlay.grab().save(str(tmp_path / "overlay.png"))
    dialog = SettingsDialog(Settings(), overlay)
    assert len(dialog.controls) == sum(len(v) for v in GROUPS.values())
    overlay.hide()


def test_real_ui_idle_and_authorized_answer(qt, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(Credentials, "get", lambda endpoint: "test-key")
    calls = []
    class Provider:
        def __init__(self, key):
            pass
        def stream(self, package, settings, cancel, on_chunk):
            calls.append(package)
            on_chunk("A streamed ")
            on_chunk("answer.")
            return (100, 20)
    monkeypatch.setattr("companion.app.OpenAIProvider", Provider)
    ledger = CostLedger(tmp_path / "usage.db", Path("config/pricing.json"))
    companion = Companion(qt, Settings(mode="hybrid", cloud_access=True, speech_output=False), ledger=ledger, runtime_hooks=False)
    for _ in range(50):
        qt.processEvents()
    assert not calls
    assert not ledger.history()
    companion.overlay.entry.setText("Explain this concept")
    companion.overlay.submit()
    pump(qt, lambda: not companion.busy)
    assert len(calls) == 1
    assert companion.overlay.answer == "A streamed answer."
    assert len(companion.engine.conversation) == 2
    assert ledger.history()[0][4] == "completed"
    companion.action("pause")
    assert companion.paused
    assert not companion.engine.frames
    companion.shutdown()
    companion.overlay.hide()
    companion.purge_timer.stop()
    companion.arm_timer.stop()


def test_permission_revocation_drops_queued_transcript(qt, tmp_path, monkeypatch):
    from companion.context import Transcript
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    ledger = CostLedger(tmp_path / "usage.db", Path("config/pricing.json"))
    companion = Companion(qt, Settings(), ledger=ledger, runtime_hooks=False)
    generation = companion.generation
    companion.action("pause")
    companion.transcript(generation, Transcript(time.time(), "Matek, what is that?", "microphone"))
    assert not companion.engine.transcripts
    assert not companion.busy
    assert not ledger.history()
    companion.shutdown()
    companion.overlay.hide()
    companion.purge_timer.stop()
    companion.arm_timer.stop()


def test_cloud_disabled_routes_old_hybrid_settings_to_ollama(qt, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    def forbidden(endpoint):
        raise AssertionError("No key lookup allowed for local replies")
    monkeypatch.setattr(Credentials, "get", forbidden)
    calls = []
    class LocalProvider:
        def stream(self, package, settings, cancel, on_chunk):
            calls.append(settings.mode)
            on_chunk("Four.")
            return None
    monkeypatch.setattr("companion.app.OllamaProvider", LocalProvider)
    cfg = Settings(mode="hybrid", cloud_access=False, speech_output=True)
    companion = Companion(qt, cfg, runtime_hooks=False)
    companion.ask("What is two plus two?")
    pump(qt, lambda: not companion.busy)
    assert calls == ["local"]
    assert companion.overlay.answer == "Four."
    assert not companion.speech.settings.speech_output
    assert not companion.ledger.history()
    companion.shutdown()
    companion.overlay.hide()
    companion.purge_timer.stop()
    companion.arm_timer.stop()
