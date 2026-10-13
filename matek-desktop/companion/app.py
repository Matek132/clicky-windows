from dataclasses import replace
from datetime import datetime
import ctypes
import json
import logging
import sys
import threading
import time

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QDialog, QMessageBox

from .audio import AudioService, join_transcript
from .config import Settings
from .context import ContextEngine
from .controller import RequestController
from .costs import CostLedger, pricing_path
from .detection import QuestionDetector
from .hotkeys import Hotkeys
from .providers import OpenAIProvider, OllamaProvider, Cancelled
from .security import Credentials
from .storage import ConversationStore
from .ui import SettingsDialog, TextDialog, ConfirmationDialog, STYLE, icon
from .mini_ui import MiniOverlay as Overlay
from .speech import SpokenAnswer
from .memory import CompanionMemory, context_intent
from .vision import ScreenObserver

log = logging.getLogger("matek")


class Signals(QObject):
    status = Signal(str)
    transcript = Signal(int, object)
    prepared = Signal(int, object)
    chunk = Signal(int, str)
    finished = Signal(int, str, str)
    action = Signal(str)
    activity = Signal(int, str, bool)


def set_autostart(enabled):
    if sys.platform != "win32":
        return
    import winreg
    from pathlib import Path
    command = f'"{sys.executable}"'
    if not getattr(sys, "frozen", False):
        command += f' "{Path(__file__).resolve().parent.parent / "main.py"}"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            winreg.SetValueEx(key, "MatekScreenCompanion", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "MatekScreenCompanion")
            except FileNotFoundError:
                pass


class Companion:
    def __init__(self, application, settings=None, ledger=None, runtime_hooks=True):
        self.application = application
        self.runtime_hooks = runtime_hooks
        self.settings = settings or Settings.load()
        self.signals = Signals()
        self.signals.status.connect(self.status)
        self.signals.transcript.connect(self.transcript)
        self.signals.prepared.connect(self.dispatch)
        self.signals.chunk.connect(self.chunk)
        self.signals.finished.connect(self.finished)
        self.signals.action.connect(self.action)
        self.signals.activity.connect(self.activity)
        self.ledger = ledger or CostLedger()
        self.controller = RequestController(self.ledger)
        self.store = ConversationStore()
        self.engine = ContextEngine(self.settings)
        self.detector = QuestionDetector(self.settings)
        self.observer = ScreenObserver(self.settings)
        self.memory = CompanionMemory(self.settings)
        self.overlay = Overlay(self.settings)
        self.overlay.ask.connect(self.ask)
        self.overlay.action.connect(self.action)
        self.overlay.position_default()
        self.speech = SpokenAnswer(self.settings)
        self.speech.text_changed.connect(self.overlay.show_words)
        self.speech.speaking_changed.connect(self.speaking_changed)
        self.speech.completed.connect(self.overlay.finish_presentation)
        self.speech.error.connect(self.status)
        self.echo_suppression = threading.Event()
        self.echo_timer = QTimer()
        self.echo_timer.setSingleShot(True)
        self.echo_timer.timeout.connect(self.echo_suppression.clear)
        self.active_audio = set()
        self.pending_question = None
        self.unfinished_question = None
        self.generation = 0
        self.request_id = 0
        self.busy = False
        self.paused = False
        self.armed_at = 0
        self.armed_until = 0
        self.audio = None
        self.capture_stop = threading.Event()
        self.cancel = threading.Event()
        self.capture_lock = threading.Lock()
        self.tray = QSystemTrayIcon(icon(), application)
        self.tray.setToolTip("Matek · local perception, answers on demand")
        menu = QMenu()
        for title, action in (("Ask Matek", "focus"), ("Show / hide", "toggle"), ("Settings", "settings"),
                              ("Pause / resume monitoring", "pause"), ("Inspect context", "inspect"),
                              ("Usage / budget history", "usage"), ("Clear recent context", "clear"),
                              ("Clear conversations", "clear_history"), ("Clear all local data", "clear_all"), ("Quit", "quit")):
            item = QAction(title, menu)
            item.triggered.connect(lambda _, a=action: self.action(a))
            menu.addAction(item)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.action("toggle") if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()
        self.hotkeys = None
        if self.settings.persistent_history:
            for _, question, answer in reversed(self.store.read(self.settings.conversation_retention_days)[:self.settings.conversation_turns]):
                self.engine.add_turn(question, answer)
        if runtime_hooks:
            self.start_hotkeys()
        self.start_capture()
        if runtime_hooks:
            set_autostart(self.settings.start_with_windows)
        self.purge_timer = QTimer()
        self.purge_timer.timeout.connect(self.maintenance)
        self.purge_timer.start(1000)
        self.arm_timer = QTimer()
        self.arm_timer.timeout.connect(self.check_arm)
        self.arm_timer.start(500)
        if not self.settings.launch_minimized:
            self.overlay.reveal()
        application.aboutToQuit.connect(self.shutdown)

    def maintenance(self):
        self.engine.purge()
        self.observer.expire()
        if self.unfinished_question and time.time() - self.unfinished_question[2] > 30:
            self.unfinished_question = None
            self.status("Please repeat the complete question")
            self.overlay.finish_presentation()

    def status(self, text):
        self.overlay.status.setText(text)
        if self.paused:
            mode = "paused"
        elif self.speech.speaking:
            mode = "speaking"
        elif "microphone" in self.active_audio:
            mode = "listening"
        elif self.busy:
            mode = "thinking"
        else:
            mode = "ready"
        self.overlay.set_mode(mode, text)
        self.tray.setToolTip("Matek · " + text[:110])

    def speaking_changed(self, speaking):
        if speaking and self.settings.echo_guard:
            self.echo_timer.stop()
            self.echo_suppression.set()
        elif not speaking and self.echo_suppression.is_set():
            # Cover the last syllable / loudspeaker tail; raw input is still open.
            self.echo_timer.start(650)
        self.status("Speaking · click companion to stop" if speaking else "Listening locally")

    def activity(self, generation, source, active):
        if generation != self.generation or self.paused:
            return
        if active:
            self.active_audio.add(source)
            if source == "microphone" and not self.echo_suppression.is_set():
                self.status("Listening · waiting for you to finish")
        else:
            self.active_audio.discard(source)

    def start_hotkeys(self):
        if self.hotkeys:
            self.hotkeys.close()
        s = self.settings
        self.hotkeys = Hotkeys({"ask_voice": s.hotkey_ask, "toggle": s.hotkey_toggle,
                               "pause": s.hotkey_pause, "clear": s.hotkey_clear, "capture": s.hotkey_capture},
                              self.signals.action.emit, self.signals.status.emit)
        self.hotkeys.start()

    def start_capture(self):
        if self.paused:
            return
        cfg = self.settings
        generation = self.generation
        stop = self.capture_stop = threading.Event()
        self.audio = AudioService(cfg, lambda snippet: self.signals.transcript.emit(generation, snippet),
                                  lambda message: self.signals.status.emit(message) if not stop.is_set() else None,
                                  lambda source, active: self.signals.activity.emit(generation, source, active),
                                  self.echo_suppression, self.memory.owns)
        self.memory.start()
        self.audio.start()
        if cfg.continuous_screen:
            threading.Thread(target=self.screen_loop, args=(generation, stop, self.observer, self.engine),
                             daemon=True, name="screen-observer").start()
        self.status("Ready · perception local · no background cloud requests")

    def stop_capture(self):
        self.memory.close()
        self.generation += 1
        self.capture_stop.set()
        if self.audio:
            self.audio.close()
        self.armed_at = self.armed_until = 0
        self.active_audio.clear()
        self.unfinished_question = None

    def screen_loop(self, generation, stop, observer, engine):
        while not stop.is_set():
            if self.memory.owns("screen"):
                stop.wait(.5)
                continue
            try:
                with self.capture_lock:
                    if stop.is_set():
                        break
                    frame = observer.capture()
                if frame and not stop.is_set() and generation == self.generation:
                    engine.add_frame(frame)
                if observer.ocr_warning and not stop.is_set():
                    self.signals.status.emit(observer.ocr_warning)
            except PermissionError as exc:
                # Discard old visuals when a sensitive window is detected.
                engine.clear()
                observer.clear()
                if not stop.is_set():
                    self.signals.status.emit(str(exc))
            except Exception:
                if not stop.is_set():
                    self.signals.status.emit("Screen capture unavailable · check monitor / permissions")
            stop.wait(observer.delay())

    def check_arm(self):
        if self.armed_until and time.time() > self.armed_until:
            self.armed_until = 0
            self.status("Spoken question timed out · press Ask shortcut again")

    def transcript(self, generation, snippet):
        if generation != self.generation or self.paused or self.echo_suppression.is_set():
            return
        if snippet.truncated:
            self.unfinished_question = None
            self.status(f"Question exceeded {self.settings.max_question_seconds}s · please split it into shorter questions")
            return
        if not snippet.is_final:
            if snippet.source == "microphone":
                self.overlay.preview_question(snippet.text)
                self.status("Still listening · long question continues")
            else:
                self.engine.add_transcript(snippet)
            return
        if snippet.source == "microphone":
            if self.unfinished_question:
                prefix, score, at = self.unfinished_question
                snippet = replace(snippet, text=join_transcript(prefix, snippet.text),
                                  confidence=min(score, snippet.confidence))
                self.unfinished_question = None
            wake = self.detector.wake_match(snippet.text)
            if self.detector.incomplete(wake.group(1) if wake else snippet.text):
                self.unfinished_question = (snippet.text, snippet.confidence, time.time())
                self.overlay.preview_question(snippet.text)
                self.status("Listening · finish your question when ready")
                return
        self.engine.add_transcript(snippet)
        manual = snippet.source == "microphone" and self.armed_until > time.time() and snippet.at >= self.armed_at
        question = self.detector.detect(snippet.text, snippet.source, snippet.confidence, manual)
        if question:
            self.armed_until = 0
            speak = snippet.source == "microphone" and self.detector.addressed(snippet.text)
            if self.busy:
                self.pending_question = (question, snippet.source, speak)
            else:
                self.ask(question, snippet.source, speak)
        elif snippet.source == "microphone" and snippet.confidence < self.settings.confidence:
            self.status("Speech unclear · please repeat, or check the microphone in Settings")

    def ask(self, question, source="typed", speak=False):
        if self.busy:
            self.pending_question = (question, source, speak)
            self.cancel_request()
            self.status("Switching to your new question…")
            return
        self.speech.cancel()
        self.speech.configure(replace(self.settings, speech_output=self.settings.speech_output and speak))
        if self.paused:
            self.status("Monitoring paused · typed question will use conversation only")
        if len(question) > 12000:
            self.status("Question is too long · maximum 12,000 characters")
            return
        self.busy = True
        self.request_id += 1
        identity = self.request_id
        self.cancel = threading.Event()
        cancel = self.cancel
        # With cloud disabled, always use the local backend, including older
        # settings that still name the former hybrid default.
        cfg = replace(self.settings, mode=self.settings.mode if self.settings.cloud_access else "local")
        generation = self.generation
        engine, observer = self.engine, self.observer
        memory = self.memory
        paused = self.paused
        self.overlay.begin(question)

        def prepare():
            try:
                if not paused and context_intent(question)[0] and not memory.owns("screen") and (cfg.manual_screenshots or cfg.continuous_screen):
                    with self.capture_lock:
                        if cancel.is_set():
                            raise Cancelled()
                        try:
                            frame = observer.capture(fresh=True)
                            if generation == self.generation and not cancel.is_set() and frame:
                                engine.add_frame(frame)
                        except PermissionError:
                            engine.clear()
                            observer.clear()
                        except Exception:
                            self.signals.status.emit("Fresh screenshot unavailable · using permitted recent context")
                if cancel.is_set() or generation != self.generation:
                    raise Cancelled()
                package = engine.select(question, source)
                if not paused:
                    package = memory.select(package)
                prepared = self.controller.prepare(package, cfg)
                self.signals.prepared.emit(identity, prepared)
            except Cancelled:
                self.signals.finished.emit(identity, "Cancelled", "")
            except Exception as exc:
                message = str(exc) if isinstance(exc, (PermissionError, ValueError)) else "Context preparation failed. Check configuration."
                self.signals.finished.emit(identity, message, "")
        threading.Thread(target=prepare, daemon=True, name="context-package").start()

    def dispatch(self, identity, prepared):
        if identity != self.request_id or self.cancel.is_set():
            self.finished(identity, "Cancelled", "")
            return
        approved = False
        if prepared.requires_confirmation:
            self.status("Awaiting approval · nothing transmitted")
            dialog = ConfirmationDialog(prepared, self.overlay)
            # Pause, cancel or settings via global shortcut rejects the live confirmation.
            self.confirmation_dialog = dialog
            approved = dialog.exec() == QDialog.Accepted
            self.confirmation_dialog = None
            if not approved or self.cancel.is_set():
                self.finished(identity, "Cancelled · nothing transmitted", "")
                return
        self.status("Thinking locally…" if prepared.settings.mode == "local" else f"Cloud request · reserved US${prepared.estimate:.5f}")
        cancel = self.cancel

        def answer():
            chunks = []
            try:
                if prepared.settings.mode == "local":
                    provider = OllamaProvider()
                else:
                    key = Credentials.get(prepared.settings.api_base)
                    if not key:
                        raise ValueError("API key missing. Add it in Settings → Intelligence. No request was sent.")
                    provider = OpenAIProvider(key)
                def emit(chunk):
                    if not cancel.is_set():
                        chunks.append(chunk)
                        self.signals.chunk.emit(identity, chunk)
                self.controller.execute(prepared, provider, cancel, emit, approved)
                if cancel.is_set():
                    raise Cancelled()
                text = "".join(chunks)
                self.signals.finished.emit(identity, "Answer ready", text)
            except Cancelled:
                self.signals.finished.emit(identity, "Cancelled · any transmitted request may still be billed", "")
            except Exception as exc:
                log.warning("answer_failure type=%s", type(exc).__name__)
                message = str(exc) if isinstance(exc, (PermissionError, ValueError, RuntimeError)) else "Connection failed. No automatic retry was made. Check network / local model."
                self.signals.finished.emit(identity, message, "")
        threading.Thread(target=answer, daemon=True, name="on-demand-answer").start()

    def chunk(self, identity, text):
        if identity == self.request_id and not self.cancel.is_set():
            self.overlay.append(text)
            self.speech.feed(text)

    def finished(self, identity, status, answer):
        if identity != self.request_id:
            return
        self.busy = False
        self.overlay.submit_button.setEnabled(True)
        self.status(status)
        if answer and not self.cancel.is_set():
            self.speech.finish()
            question = self.overlay.question.text()
            self.engine.add_turn(question, answer)
            if self.settings.persistent_history:
                try:
                    self.store.save(question, answer, self.settings.conversation_retention_days)
                except Exception:
                    self.status("Answer ready · saving history failed")
        elif not self.overlay.answer:
            self.overlay.browser.setPlainText(status)
            self.overlay.finish_presentation()
        pending = self.pending_question
        self.pending_question = None
        if pending and not self.paused:
            QTimer.singleShot(0, lambda: self.ask(*pending))

    def cancel_request(self):
        self.cancel.set()
        self.speech.cancel()
        dialog = getattr(self, "confirmation_dialog", None)
        if dialog:
            dialog.reject()
        # Keep busy until worker exits to prevent overlapping / unaccounted requests.

    def action(self, action):
        if action == "quit":
            self.application.quit()
        elif action in {"hide", "toggle"}:
            self.overlay.hide() if action == "hide" or self.overlay.isVisible() else self.overlay.reveal(focus=True)
        elif action == "focus":
            self.overlay.reveal(focus=True)
        elif action == "collapse":
            self.overlay.collapse()
        elif action == "stop_voice":
            self.pending_question = None
            self.cancel_request()
            self.overlay.controls.show()
            self.overlay.update_mask()
            self.overlay.finish_presentation()
            self.status("Stopped · listening locally")
        elif action == "copy":
            self.application.clipboard().setText(self.overlay.answer)
        elif action == "expand":
            if self.overlay.answer:
                self.ask("Explain your previous answer in greater detail, with examples.")
        elif action == "cancel":
            self.cancel_request()
            self.status("Cancelling request…")
        elif action == "ask_voice":
            if self.paused or not self.settings.microphone:
                self.overlay.reveal(focus=True)
                self.status("Microphone disabled / paused · type a question or enable microphone permission")
            else:
                self.armed_at = time.time()
                self.armed_until = time.time() + 25
                self.status("Ask now · next microphone utterance armed for 25 seconds")
        elif action == "capture":
            if self.paused or not self.settings.manual_screenshots:
                self.status("Manual screenshots disabled / paused · enable permission in Settings")
            else:
                self.ask("Explain what is visible on my screen.", "manual")
        elif action == "pause":
            self.pending_question = None
            self.cancel_request()
            self.stop_capture()
            self.engine.clear()
            self.observer.clear()
            self.paused = not self.paused
            external = self.settings.memory_backend == "screenpipe"
            self.overlay.permissions.setText(("MATEK PAUSED · SCREENPIPE IS SEPARATE" if external else "ALL CAPTURE PAUSED") if self.paused else "Capture permissions restored")
            if not self.paused:
                self.start_capture()
                self.overlay.apply(self.settings)
            self.status(("Matek paused · stop the separate Screenpipe recorder separately" if external else "All capture paused · recent context purged") if self.paused else "Local monitoring resumed")
        elif action == "clear":
            self.pending_question = None
            self.unfinished_question = None
            self.cancel_request()
            self.engine.clear()
            self.observer.clear()
            self.status("Recent screen and audio context cleared")
        elif action == "clear_history":
            self.pending_question = None
            self.unfinished_question = None
            self.cancel_request()
            self.engine.clear(conversation=True)
            self.observer.clear()
            self.store.clear()
            self.overlay.answer = ""
            self.overlay.browser.clear()
            self.overlay.question.clear()
            self.overlay.entry.clear()
            self.status("Conversation and recent context cleared")
        elif action == "clear_all":
            self.pending_question = None
            self.cancel_request()
            self.stop_capture()
            self.paused = True
            self.engine.clear(conversation=True)
            self.observer.clear()
            self.store.clear()
            try:
                Credentials.set(self.settings.api_base, "")
                Credentials.set("screenpipe:" + self.settings.screenpipe_url, "")
                self.settings = Settings()
                self.memory = CompanionMemory(self.settings)
                self.settings.save()
                set_autostart(False)
                self.overlay.apply(self.settings)
            except Exception:
                self.status("Data clearing incomplete · credential or settings removal failed")
                return
            self.overlay.answer = ""
            self.overlay.browser.clear()
            self.overlay.question.clear()
            self.overlay.entry.clear()
            self.status("Capture paused · context, conversation, settings and current API key cleared; usage ledger retained for budget protection")
        elif action == "inspect":
            with self.engine.lock:
                text = json.dumps(self.engine.inspect(), indent=2) + "\n\nRecent OCR / transcripts:\n"
                text += "\n".join(f"{f.app}: {f.ocr}" for f in self.engine.frames)
                text += "\n".join(f"{t.source}: {t.text}" for t in self.engine.transcripts)
            TextDialog("Local context (RAM)", text, self.overlay).exec()
        elif action == "history":
            with self.engine.lock:
                text = "\n\n".join(f"{role.upper()}\n{body}" for role, body in self.engine.conversation)
            TextDialog("Conversation history", text or "No conversation yet.", self.overlay).exec()
        elif action == "usage":
            totals = self.ledger.totals()
            text = f"Today US${totals[0]:.5f} · Month US${totals[1]:.5f}\nPricing file: {pricing_path()}\n\n"
            for at, model, estimated, charged, status, incoming, outgoing in self.ledger.history():
                text += f"{datetime.fromtimestamp(at):%Y-%m-%d %H:%M} | {model} | estimated ${estimated:.5f} | accounted ${charged:.5f} | {status} | tokens {incoming}/{outgoing}\n"
            text += "\nUnknown/failed/cancelled requests retain their reservation. Local estimates are not provider hard limits."
            TextDialog("Usage and reservations · USD", text, self.overlay).exec()
        elif action == "settings":
            self.pending_question = None
            self.cancel_request()
            dialog = SettingsDialog(self.settings, self.overlay)
            if dialog.exec() == QDialog.Accepted:
                self.stop_capture()
                self.engine.clear(conversation=True)
                self.settings = dialog.result_settings
                self.speech.configure(self.settings)
                self.engine = ContextEngine(self.settings)
                self.detector = QuestionDetector(self.settings)
                self.observer = ScreenObserver(self.settings)
                self.memory = CompanionMemory(self.settings)
                self.overlay.apply(self.settings)
                self.overlay.position_default()
                self.overlay.reveal()
                self.start_hotkeys()
                try:
                    set_autostart(self.settings.start_with_windows)
                except OSError:
                    self.status("Windows startup registration failed")
                self.start_capture()

    def shutdown(self):
        self.memory.close()
        self.cancel_request()
        self.stop_capture()
        if self.hotkeys:
            self.hotkeys.close()
        self.tray.hide()
        self.engine.clear(conversation=True)
        self.observer.clear()
        self.settings.overlay_x, self.settings.overlay_y = self.overlay.x(), self.overlay.y()
        try:
            self.settings.save()
        except Exception:
            pass


def run(smoke=False):
    app = QApplication(sys.argv)
    app.setApplicationName("Matek Screen Companion")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)
    mutex = None
    if sys.platform == "win32" and not smoke:
        kernel = ctypes.windll.kernel32
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        mutex = kernel.CreateMutexW(None, False, "Local\\MatekScreenCompanion")
        if kernel.GetLastError() == 183:
            kernel.CloseHandle(mutex)
            QMessageBox.information(None, "Matek", "Matek is already running. Use its system tray icon or Ctrl+Alt+O.")
            return 0
    try:
        cfg = Settings() if smoke else Settings.load()
    except Exception:
        QMessageBox.warning(None, "Matek settings", "Settings are invalid. Safe defaults loaded; all capture and cloud permissions are off.")
        cfg = Settings()
    companion = Companion(app, cfg, runtime_hooks=not smoke)
    # Supported Windows 10+ overlay exclusion. Failure is surfaced instead of concealed.
    if sys.platform == "win32":
        user = ctypes.windll.user32
        user.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        if not user.SetWindowDisplayAffinity(int(companion.overlay.winId()), 0x11):
            companion.status("Ready · Windows could not exclude overlay from capture")
    if smoke:
        QTimer.singleShot(700, app.quit)
    result = app.exec()
    if mutex:
        ctypes.windll.kernel32.CloseHandle(mutex)
    return result
