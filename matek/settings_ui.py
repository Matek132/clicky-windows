"""PyQt6 controls for local perception, voice, routing, privacy and spending."""
from dataclasses import asdict
import threading
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QScrollArea, QFormLayout, QCheckBox,
                            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QLabel, QPushButton, QDialogButtonBox)
from .config import Settings
from .security import Credentials


GROUPS = {
    "Listening": ["microphone", "mic_device", "activation", "wake_words", "confidence", "mic_gain", "mic_noise_floor", "end_pause_seconds", "max_question_seconds", "interrupt_questions", "echo_guard", "allow_voice_commands_during_speech", "whisper_model", "language"],
    "Screen / audio": ["continuous_screen", "manual_screenshots", "system_audio", "system_device", "system_questions", "monitor", "capture_seconds", "retention_seconds", "max_frames", "screen_memory_mb", "image_max_side", "max_request_images", "ocr", "tesseract_path"],
    "Intelligence": ["mode", "local_provider", "local_url", "local_model", "local_text_model", "local_vision", "lmstudio_url", "cloud_provider", "model", "api_base", "cloud_access", "escalation", "web_access", "verbosity", "max_output_tokens", "preset", "knowledge_enabled", "knowledge_folder"],
    "Voice": ["speech_output", "speech_policy", "response_language", "speech_voice", "speech_volume", "speech_rate", "answer_display_seconds"],
    "Privacy / memory": ["exclusions", "persistent_history", "conversation_turns", "conversation_retention_days", "memory_backend", "screenpipe_url", "screenpipe_retention_days", "proactive"],
    "Budget": ["per_question_usd", "daily_usd", "monthly_usd", "confirm_above_usd"],
    "Interface": ["always_on_top", "opacity", "cursor_mode", "start_with_windows", "launch_minimized"],
}
CHOICES = {"mode": ["local", "hybrid", "cloud", "confirm"], "local_provider": ["ollama", "lmstudio"], "activation": ["automatic", "wake", "push"],
           "cloud_provider": ["openai", "claude", "gemini", "copilot"], "escalation": ["ask", "budget", "never"],
           "speech_policy": ["wake", "full", "summary", "text", "auto"], "verbosity": ["quick", "balanced", "detailed", "research"],
           "preset": ["balanced", "gaming", "research", "programming", "study", "media"], "memory_backend": ["ram", "screenpipe"]}


class MatekSettingsDialog(QDialog):
    status_result = pyqtSignal(str)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Matek settings · Clicky for Windows")
        self.resize(690, 650)
        layout = QVBoxLayout(self)
        note = QLabel("Monitoring is local and opt-in. Local Only makes no paid requests.\n"
                      "Say Matek for speech in wake speech policy; choose full to speak every answer.\n"
                      "Echo guard accepts Stop during speech; headphones improve interruption reliability.")
        note.setWordWrap(True)
        layout.addWidget(note)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.controls = {}
        raw = asdict(manager.settings)
        for name, fields in GROUPS.items():
            page = QWidget()
            form = QFormLayout(page)
            for key in fields:
                value = raw[key]
                if key in CHOICES:
                    control = QComboBox()
                    control.addItems(CHOICES[key])
                    control.setCurrentText(str(value))
                elif type(value) is bool:
                    control = QCheckBox("Enabled")
                    control.setChecked(value)
                elif type(value) is int:
                    control = QSpinBox()
                    control.setRange(-1, 100000)
                    control.setValue(value)
                elif type(value) is float:
                    control = QDoubleSpinBox()
                    control.setRange(-.5 if key == "speech_rate" else 0, 1000)
                    control.setDecimals(3)
                    control.setValue(value)
                else:
                    control = QLineEdit(str(value))
                self.controls[key] = control
                form.addRow(key.replace("_", " ").capitalize(), control)
            if name == "Voice":
                voices = manager.speech.tts.availableVoices() if manager.speech.tts else []
                form.addRow(QLabel("Installed offline voices: " + ", ".join(v.name() for v in voices)))
            if name == "Privacy / memory":
                self.memory_key = QLineEdit()
                self.memory_key.setEchoMode(QLineEdit.EchoMode.Password)
                self.memory_key.setPlaceholderText("Blank keeps existing token")
                form.addRow("Screenpipe token · Windows vault", self.memory_key)
                form.addRow(QLabel("Screenpipe is a separate recorder; disable its microphone recording.\nPausing Matek does not stop that recorder."))
                retention = QPushButton("Apply saved Screenpipe retention · may delete old recordings")
                retention.clicked.connect(self.retention)
                form.addRow(retention)
            if name == "Listening":
                button = QPushButton("List microphone and loopback device IDs")
                button.clicked.connect(self.list_devices)
                form.addRow(button)
            if name == "Budget":
                button = QPushButton("View provider usage and spending reservations")
                button.clicked.connect(self.usage)
                form.addRow(button)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            tabs.addTab(scroll, name)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.status_result.connect(self.status.setText)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        raw = asdict(self.manager.settings)
        for key, control in self.controls.items():
            if isinstance(control, QComboBox):
                raw[key] = control.currentText()
            elif isinstance(control, QCheckBox):
                raw[key] = control.isChecked()
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                raw[key] = control.value()
            else:
                raw[key] = control.text().strip()
        try:
            settings = Settings(**raw)
            settings.validate()
            if self.memory_key.text():
                Credentials.set("screenpipe:" + settings.screenpipe_url, self.memory_key.text().strip())
            self.manager.apply_settings(settings)
            self.accept()
        except Exception as exc:
            self.status.setText(str(exc) if isinstance(exc, ValueError) else "Settings could not be saved")

    def retention(self):
        client = self.manager._memory.external.client
        def work():
            try:
                client.configure_retention()
                self.status_result.emit("Saved retention applied to Screenpipe")
            except Exception:
                self.status_result.emit("Retention not applied · check local service and saved token")
        threading.Thread(target=work, daemon=True).start()

    def list_devices(self):
        from .audio import devices
        from PyQt6.QtWidgets import QMessageBox
        try:
            QMessageBox.information(self, "Local audio IDs", "\n".join(f"{row['index']}: {row['name']} {'[loopback]' if row['loopback'] else ''}" for row in devices()))
        except Exception:
            self.status.setText("Audio device enumeration failed")

    def usage(self):
        from PyQt6.QtWidgets import QMessageBox
        rows = self.manager.ledger.history()
        QMessageBox.information(self, "Usage · USD", "\n".join(f"{row[7]} {row[1]} · reserved ${row[2]:.5f} · accounted ${row[3]:.5f} · {row[4]}" for row in rows)
                                or "No paid requests. Local Ollama/LM Studio requests are not billed.")
