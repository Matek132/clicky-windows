"""Optional local memory controls, independent of reasoning-provider settings."""
from dataclasses import replace
import threading
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QFormLayout, QCheckBox, QLineEdit, QSpinBox, QLabel, QPushButton, QDialogButtonBox


class MemoryDialog(QDialog):
    result_ready = pyqtSignal(str)

    def __init__(self, memory, parent=None):
        super().__init__(parent)
        self.memory = memory
        self.setWindowTitle("Matek · Local memory")
        form = QFormLayout(self)
        self.enabled, self.screen, self.audio = QCheckBox(), QCheckBox(), QCheckBox()
        self.enabled.setChecked(memory.settings.enabled)
        self.screen.setChecked(memory.settings.screen)
        self.audio.setChecked(memory.settings.audio)
        form.addRow("Use separate Screenpipe service", self.enabled)
        form.addRow("Screen history / two-minute RAM fallback", self.screen)
        form.addRow("Retrieve Screenpipe audio history", self.audio)
        self.url = QLineEdit(memory.settings.url)
        self.filters = QLineEdit(memory.settings.exclusions)
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(memory.settings.retention_days)
        form.addRow("Local API", self.url)
        form.addRow("Exclude matching apps, titles, text", self.filters)
        form.addRow("Maximum history days", self.days)
        hint = QLabel("Set SCREENPIPE_LOCAL_API_KEY in the launch environment; it is not saved here.\n"
                      "Configure Screenpipe to capture screen and system audio only; Clicky owns the mic.\n"
                      "These filters protect retrieval; also configure recording exclusions in Screenpipe.\n"
                      "Disabling this adapter does not stop or delete the separate recorder's files.")
        hint.setWordWrap(True)
        form.addRow(hint)
        self.status = QLabel(memory.status)
        form.addRow(self.status)
        retention = QPushButton("Apply saved retention to Screenpipe (older recordings may be deleted)")
        retention.clicked.connect(self.retention)
        form.addRow(retention)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.result_ready.connect(self.status.setText)

    def save(self):
        try:
            settings = replace(self.memory.settings, enabled=self.enabled.isChecked(), screen=self.screen.isChecked(),
                               audio=self.audio.isChecked(), url=self.url.text().strip(),
                               exclusions=self.filters.text(), retention_days=self.days.value())
            settings.save()
            self.memory.settings = settings
            self.memory.screenpipe_active = False
            with self.memory.lock:
                self.memory.rows.clear()
            self.accept()
        except Exception:
            self.status.setText("Could not save: check local URL and settings permissions.")

    def retention(self):
        def apply():
            try:
                self.memory.configure_retention()
                self.result_ready.emit("Saved retention policy applied to Screenpipe")
            except Exception:
                self.result_ready.emit("Retention not applied · check service and local API authentication")
        threading.Thread(target=apply, daemon=True).start()
