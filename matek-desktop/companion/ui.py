from dataclasses import asdict, fields
from datetime import datetime
import json
import sys
import ctypes
import threading
from PySide6.QtCore import Qt, Signal, QPoint, QPropertyAnimation
from PySide6.QtGui import QFont, QIcon, QPainter, QColor, QPixmap
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QLineEdit, QDialog, QTabWidget, QScrollArea, QFormLayout, QCheckBox, QComboBox,
    QSpinBox, QDoubleSpinBox, QDialogButtonBox, QMessageBox, QSizeGrip, QPlainTextEdit)
from .config import Settings
from .security import Credentials
from .hotkeys import parse_hotkey

STYLE = """
QWidget { background:#101722; color:#e7edf6; font-family:'Segoe UI'; font-size:13px; }
QWidget#surface { border:1px solid #2b3c52; border-radius:18px; }
QLabel#brand { font-size:18px; font-weight:600; color:#f5f8ff; }
QLabel#status { color:#8ecfc5; font-size:12px; }
QLabel#muted { color:#93a4bc; }
QPushButton { background:#1f2c3e; border:1px solid #30445d; padding:8px 12px; border-radius:8px; }
QPushButton:hover { background:#2d4059; }
QPushButton:disabled { color:#637186; }
QPushButton#primary { background:#397e73; border:1px solid #58a395; font-weight:600; }
QLineEdit,QPlainTextEdit,QTextBrowser,QSpinBox,QDoubleSpinBox,QComboBox { background:#151f2e;
 border:1px solid #2b3c52; border-radius:8px; padding:8px; selection-background-color:#397e73; }
QTextBrowser { border:0; padding:4px; font-size:14px; }
QTabWidget::pane { border:1px solid #2b3c52; }
QTabBar::tab { background:#1a2636; padding:9px; }
QTabBar::tab:selected { background:#397e73; }
QScrollBar:vertical { background:#151f2e; width:10px; }
QScrollBar::handle:vertical { background:#344861; min-height:30px; border-radius:5px; }
"""


def icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#397e73"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 16, 16)
    painter.setPen(QColor("#f4fffa"))
    painter.setFont(QFont("Segoe UI", 28, QFont.Bold))
    painter.drawText(pix.rect(), Qt.AlignCenter, "M")
    painter.end()
    return QIcon(pix)


class DragHeader(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, "offset"):
            self.window().move(event.globalPosition().toPoint() - self.offset)


class Overlay(QWidget):
    ask = Signal(str)
    action = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.answer = ""
        self.collapsed = False
        self.setObjectName("surface")
        self.setWindowTitle("Matek Screen Companion")
        self.setWindowIcon(icon())
        flags = Qt.Tool | Qt.FramelessWindowHint
        if settings.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMinimumSize(350, 150)
        self.resize(440, 610)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 12)
        header = DragHeader()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        brand = QLabel("M  /  MATEK")
        brand.setObjectName("brand")
        brand.setAttribute(Qt.WA_TransparentForMouseEvents)
        row.addWidget(brand)
        row.addStretch()
        for text, action in (("−", "collapse"), ("⚙", "settings"), ("×", "hide")):
            button = QPushButton(text)
            button.setFixedWidth(38)
            button.clicked.connect(lambda _, a=action: self.action.emit(a))
            row.addWidget(button)
        root.addWidget(header)
        self.status = QLabel("Ready · local background · £0 API usage")
        self.status.setWordWrap(True)
        self.status.setObjectName("status")
        root.addWidget(self.status)
        self.permissions = QLabel()
        self.permissions.setObjectName("muted")
        self.permissions.setWordWrap(True)
        root.addWidget(self.permissions)
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 10, 0, 0)
        self.question = QLabel("Your companion, ready when you are.")
        self.question.setWordWrap(True)
        self.question.setTextFormat(Qt.PlainText)
        body.addWidget(self.question)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setMarkdown("### A little context. A clearer answer.\n\nChoose permissions in **Settings**, then type a question or use **Ctrl+Alt+Space** to arm a spoken question.\n\nBackground perception stays on your computer. Cloud answers require enabled access and an authorized question.")
        body.addWidget(self.browser, 1)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Ask about your screen…")
        self.entry.setMaxLength(12000)
        self.entry.returnPressed.connect(self.submit)
        body.addWidget(self.entry)
        controls = QHBoxLayout()
        self.submit_button = QPushButton("Ask Matek")
        self.submit_button.setObjectName("primary")
        self.submit_button.clicked.connect(self.submit)
        controls.addWidget(self.submit_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(lambda: self.action.emit("cancel"))
        controls.addWidget(self.cancel_button)
        pause = QPushButton("Pause")
        pause.clicked.connect(lambda: self.action.emit("pause"))
        controls.addWidget(pause)
        body.addLayout(controls)
        footer = QHBoxLayout()
        for text, action in (("Copy", "copy"), ("Expand", "expand"), ("History", "history"), ("Clear", "clear")):
            button = QPushButton(text)
            button.clicked.connect(lambda _, a=action: self.action.emit(a))
            footer.addWidget(button)
        body.addLayout(footer)
        root.addWidget(self.body, 1)
        grip = QSizeGrip(self)
        root.addWidget(grip, 0, Qt.AlignRight)
        self.apply(settings)

    def submit(self):
        question = self.entry.text().strip()
        if question:
            self.ask.emit(question)

    def apply(self, settings):
        self.settings = settings
        self.setWindowFlag(Qt.WindowStaysOnTopHint, settings.always_on_top)
        self.setWindowOpacity(settings.opacity)
        self.permissions.setText(" · ".join(f"{name} {'on' if enabled else 'off'}" for name, enabled in
                                           (("Mic", settings.microphone), ("System", settings.system_audio),
                                            ("Screen", settings.continuous_screen), ("Cloud", settings.cloud_access))))
        self.setWindowFlag(Qt.WindowTransparentForInput, settings.click_through)

    def position_default(self):
        screen_list = QApplication.screens()
        screen = screen_list[min(self.settings.monitor - 1, len(screen_list) - 1)]
        area = screen.availableGeometry()
        self.resize(min(440, area.width() - 24), min(610, area.height() - 24))
        x, y = self.settings.overlay_x, self.settings.overlay_y
        if x < 0 or not any(s.availableGeometry().contains(QPoint(x, y)) for s in screen_list):
            x, y = area.right() - self.width() - 22, area.top() + max(12, (area.height() - self.height()) // 2)
        self.move(x, y)

    def reveal(self, focus=False):
        if focus:
            self.setWindowFlag(Qt.WindowTransparentForInput, False)
        self.show()
        if sys.platform == "win32":
            user = ctypes.windll.user32
            user.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user.SetWindowDisplayAffinity(int(self.winId()), 0x11)
        self.raise_()
        if focus:
            self.activateWindow()
            self.entry.setFocus()
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(180)
        self.animation.setStartValue(0.5)
        self.animation.setEndValue(self.settings.opacity)
        self.animation.start()

    def begin(self, question):
        self.answer = ""
        self.question.setText(question)
        self.entry.clear()
        self.browser.setMarkdown("*Preparing relevant context locally…*")
        self.submit_button.setEnabled(False)
        self.reveal()

    def append(self, chunk):
        self.answer += chunk
        self.browser.setMarkdown(self.answer)
        self.browser.verticalScrollBar().setValue(self.browser.verticalScrollBar().maximum())

    def collapse(self):
        self.collapsed = not self.collapsed
        self.body.setVisible(not self.collapsed)
        self.resize(self.width(), 155 if self.collapsed else 610)

    def closeEvent(self, event):
        event.ignore()
        self.hide()


GROUPS = {
    "General": ["mode", "preset", "monitor", "opacity", "always_on_top", "click_through", "launch_minimized", "start_with_windows"],
    "Audio": ["mic_device", "system_device", "activation", "system_questions", "wake_words", "confidence", "debounce_seconds",
              "vad_aggressiveness", "mic_gain", "mic_noise_floor", "end_pause_seconds", "max_question_seconds",
              "whisper_model", "whisper_device", "whisper_threads", "language"],
    "Voice": ["speech_output", "speech_voice", "speech_rate", "speech_volume", "echo_guard", "answer_display_seconds"],
    "Vision": ["capture_seconds", "retention_seconds", "screen_memory_mb", "max_frames", "image_max_side", "max_request_images", "ocr", "tesseract_path", "exclusions"],
    "Memory": ["memory_backend", "screenpipe_url", "screenpipe_retention_days"],
    "Intelligence": ["model", "api_base", "local_url", "local_model", "local_vision", "knowledge_enabled", "knowledge_folder", "verbosity", "max_output_tokens", "conversation_turns", "conversation_retention_days"],
    "Budget": ["daily_usd", "monthly_usd", "per_question_usd", "confirm_above_usd"],
    "Hotkeys": ["hotkey_ask", "hotkey_toggle", "hotkey_pause", "hotkey_clear", "hotkey_capture"],
    "Privacy": ["microphone", "system_audio", "continuous_screen", "manual_screenshots", "cloud_access", "persistent_history"],
}
CHOICES = {"mode": ["hybrid", "confirm", "local"], "activation": ["push", "wake", "automatic"],
           "memory_backend": ["ram", "screenpipe"],
           "whisper_device": ["cpu", "cuda"], "verbosity": ["quick", "balanced", "detailed", "research"],
           "preset": ["balanced", "gaming", "programming", "study", "research", "media"]}


class SettingsDialog(QDialog):
    memory_result = Signal(str)
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Matek · Settings")
        self.resize(810, 650)
        self.original = settings
        self.controls = {}
        self.result_settings = None
        root = QVBoxLayout(self)
        hint = QLabel("Permissions are independent. Changes restart local capture and clear recent context.\n"
                      "Budgets use USD to match provider billing. Wake phrases are detected after local transcription.")
        hint.setWordWrap(True)
        root.addWidget(hint)
        tabs = QTabWidget()
        root.addWidget(tabs)
        raw = asdict(settings)
        for group, names in GROUPS.items():
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            page = QWidget()
            form = QFormLayout(page)
            for name in names:
                value = raw[name]
                if name in CHOICES:
                    control = QComboBox()
                    control.addItems(CHOICES[name])
                    control.setCurrentText(value)
                elif isinstance(value, bool):
                    control = QCheckBox("Enabled")
                    control.setChecked(value)
                elif isinstance(value, int):
                    control = QSpinBox()
                    control.setRange(-1, 100000)
                    control.setValue(value)
                elif isinstance(value, float):
                    control = QDoubleSpinBox()
                    control.setRange(0, 1000)
                    control.setDecimals(3)
                    control.setValue(value)
                else:
                    control = QLineEdit(value)
                self.controls[name] = control
                form.addRow(name.replace("_", " ").capitalize(), control)
            if group == "Intelligence":
                self.key = QLineEdit()
                self.key.setEchoMode(QLineEdit.Password)
                self.key.setPlaceholderText("Leave blank to keep stored credential")
                form.addRow("API key (Windows vault)", self.key)
                self.remove_key = QCheckBox("Delete credential for the selected endpoint")
                form.addRow(self.remove_key)
            if group == "Audio":
                button = QPushButton("List available audio device IDs")
                button.clicked.connect(self.list_devices)
                form.addRow(button)
                form.addRow(QLabel("Device -1 follows the system default. System source requires a loopback ID."))
                form.addRow(QLabel("End pause seconds: wait this long before answering (default 4). Long questions are joined across chunks."))
            if group == "Memory":
                self.memory_key = QLineEdit()
                self.memory_key.setEchoMode(QLineEdit.Password)
                self.memory_key.setPlaceholderText("Blank keeps existing local API token")
                form.addRow("Screenpipe token (Windows vault)", self.memory_key)
                self.remove_memory_key = QCheckBox("Delete Screenpipe token for selected URL")
                form.addRow(self.remove_memory_key)
                note = QLabel("RAM: two-minute local memory. Screenpipe: optional separate recorder on this PC.\n"
                              "Screenpipe must record screen/system audio only; Matek keeps microphone ownership.\n"
                              "Configure exclusions in Screenpipe too. Disabling this adapter does not stop its recorder.")
                note.setWordWrap(True)
                form.addRow(note)
                self.memory_status = QLabel("No Screenpipe request is made until enabled or retention is applied.")
                self.memory_status.setWordWrap(True)
                self.memory_result.connect(self.memory_status.setText)
                form.addRow(self.memory_status)
                button = QPushButton("Apply saved retention to Screenpipe · older recordings may be deleted")
                button.clicked.connect(self.apply_memory_retention)
                form.addRow(button)
            if group == "Voice":
                from PySide6.QtTextToSpeech import QTextToSpeech
                engine = QTextToSpeech("sapi")
                form.addRow(QLabel("Installed offline voices: " + ", ".join(v.name() for v in engine.availableVoices())))
                form.addRow(QLabel("Speech output applies when you say 'Matek' before a question. Ordinary and typed questions display silently."))
                form.addRow(QLabel("Blank voice uses Windows default. Echo guard ignores recognition during replies; headphones allow disabling it."))
            if group == "Vision":
                button = QPushButton("List connected monitors")
                button.clicked.connect(self.list_monitors)
                form.addRow(button)
                form.addRow(QLabel("Exclusions: comma-separated app/title terms. Overlapping sensitive windows block the whole monitor."))
            scroll.setWidget(page)
            tabs.addTab(scroll, group)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def list_monitors(self):
        try:
            import mss
            with mss.mss() as capture:
                text = "\n".join(f"{i}: {m['width']} × {m['height']} at ({m['left']}, {m['top']})" for i, m in enumerate(capture.monitors) if i)
            TextDialog("Connected monitor IDs", text, self).exec()
        except Exception:
            QMessageBox.warning(self, "Monitors", "Monitor enumeration failed.")

    def apply_memory_retention(self):
        from .memory import CompanionMemory
        memory = CompanionMemory(self.original)
        def apply():
            try:
                memory.client.configure_retention()
                self.memory_result.emit("Saved retention policy applied to the separate recorder.")
            except Exception:
                self.memory_result.emit("Retention was not applied · check service and saved API token.")
            finally:
                memory.close()
        threading.Thread(target=apply, daemon=True).start()

    def list_devices(self):
        try:
            from .audio import devices
            items = devices()
            text = "\n".join(f"{d['index']}: {d['name']} {'[loopback]' if d['loopback'] else ''}" for d in items)
            viewer = TextDialog("Audio devices", text, self)
            viewer.exec()
        except Exception:
            QMessageBox.warning(self, "Audio", "Device enumeration failed. Check the audio driver and Windows permissions.")

    def save(self):
        raw = asdict(self.original)
        for name, control in self.controls.items():
            if isinstance(control, QComboBox):
                raw[name] = control.currentText()
            elif isinstance(control, QCheckBox):
                raw[name] = control.isChecked()
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                raw[name] = control.value()
            else:
                raw[name] = control.text().strip()
        try:
            settings = Settings(**raw)
            settings.validate()
            shortcuts = [parse_hotkey(raw[n]) for n in raw if n.startswith("hotkey_")]
            if len(set(shortcuts)) != len(shortcuts):
                raise ValueError("Hotkeys must be distinct.")
            if self.key.text() or self.remove_key.isChecked():
                Credentials.set(settings.api_base, "" if self.remove_key.isChecked() else self.key.text().strip())
            if self.memory_key.text() or self.remove_memory_key.isChecked():
                Credentials.set("screenpipe:" + settings.screenpipe_url, "" if self.remove_memory_key.isChecked() else self.memory_key.text().strip())
            settings.save()
            self.result_settings = settings
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Could not save settings", str(exc) if isinstance(exc, ValueError) else "Unable to save settings or secure credential.")


class TextDialog(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(780, 550)
        root = QVBoxLayout(self)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)
        root.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        root.addWidget(buttons)


class ConfirmationDialog(QDialog):
    def __init__(self, prepared, parent):
        super().__init__(parent)
        self.setWindowTitle("Approve cloud transmission")
        self.resize(560, 540)
        root = QVBoxLayout(self)
        p = prepared.package
        label = QLabel(f"Destination: {prepared.settings.api_base}\nModel: {prepared.settings.model}\n"
                       f"Estimated reservation: US${prepared.estimate:.5f}\n"
                       f"Data: question, {len(p.frames)} screenshots with OCR / window titles, "
                       f"{len(p.transcripts)} transcript snippets, {len(p.conversation)} conversation messages, "
                       f"{len(p.references)} local reference excerpts.\n"
                       "Provider billing may differ. No raw audio is transmitted.")
        label.setWordWrap(True)
        root.addWidget(label)
        preview = QPlainTextEdit(p.text() + "\n\nConversation:\n" + json.dumps(p.conversation, ensure_ascii=False))
        preview.setReadOnly(True)
        root.addWidget(preview)
        if p.frames:
            row = QHBoxLayout()
            for frame in p.frames:
                pix = QPixmap()
                pix.loadFromData(frame.jpeg)
                thumbnail = QLabel()
                thumbnail.setPixmap(pix.scaled(160, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                row.addWidget(thumbnail)
            root.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Approve and send")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
