import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor
from companion.config import Settings
from companion.mini_ui import MiniOverlay
from companion.app import Companion
from companion.context import Transcript
from companion.costs import CostLedger


def test_mascot_hover_and_popup(monkeypatch):
    app = QApplication.instance() or QApplication([])
    overlay = MiniOverlay(Settings())
    overlay.reveal()
    app.processEvents()
    assert overlay.body.isHidden() and overlay.controls.isHidden()
    assert overlay.mask().boundingRect().width() < 100
    monkeypatch.setattr(QCursor, "pos", lambda: overlay.mapToGlobal(overlay.mascot.geometry().center()))
    overlay.update_hover()
    assert not overlay.controls.isHidden()
    overlay.begin("How do I craft a lantern?")
    overlay.append("Use eight iron nuggets and one torch.")
    overlay.show_words("Use eight")
    assert overlay.browser.toPlainText() == "Use eight"
    assert overlay.answer == "Use eight iron nuggets and one torch."
    overlay.dismiss()
    assert overlay.body.isHidden()
    overlay.hide()
    overlay.hover_timer.stop()
    overlay.mascot.timer.stop()


def test_only_final_complete_microphone_question_asks(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("companion.app.AudioService.start", lambda self: None)
    cfg = Settings(mode="local", microphone=True, activation="automatic", speech_output=False)
    ledger = CostLedger(tmp_path / "usage.db", Path("config/pricing.json"))
    companion = Companion(app, cfg, ledger, runtime_hooks=False)
    requests = []
    monkeypatch.setattr(companion, "ask", lambda question, source="typed", speak=False: requests.append((question, source, speak)))
    generation = companion.generation
    companion.transcript(generation, Transcript(time.time(), "How do I", "microphone", is_final=False, session=10))
    assert requests == []
    companion.transcript(generation, Transcript(time.time(), "How do I craft a lantern?", "microphone", session=10))
    assert requests == [("How do I craft a lantern?", "microphone", False)]
    companion.transcript(generation, Transcript(time.time(), "Why is this", "microphone", session=11, truncated=True))
    assert len(requests) == 1
    companion.echo_suppression.set()
    companion.transcript(generation, Transcript(time.time(), "What does this mean?", "microphone"))
    assert len(requests) == 1
    companion.echo_suppression.clear()
    companion.busy = True
    companion.activity(generation, "microphone", True)
    assert not companion.cancel.is_set()
    companion.detector.last = -1e12
    companion.transcript(generation, Transcript(time.time(), "Matek, what is a lantern?", "microphone"))
    assert companion.pending_question == ("what is a lantern?", "microphone", True)
    assert not companion.cancel.is_set()
    companion.pending_question = None
    companion.shutdown()
    companion.overlay.hide()
    companion.purge_timer.stop()
    companion.arm_timer.stop()
    companion.echo_timer.stop()
