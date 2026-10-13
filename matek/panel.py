"""Extend Clicky's existing floating panel with compact, conversational controls."""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QLabel, QLineEdit, QPushButton, QHBoxLayout,
                            QSizeGrip, QDialog, QVBoxLayout, QPlainTextEdit, QMessageBox)
from ui.panel import CompanionPanel, AppState
from .settings_ui import MatekSettingsDialog


class MatekPanel(CompanionPanel):
    settings_applied = pyqtSignal()

    def __init__(self, manager):
        self.manager = manager
        self._expanded = True
        self._full_answer = ""
        super().__init__()
        self.setMinimumSize(260, 56)
        self.setMaximumSize(10000, 10000)
        self.resize(430, 460)
        self.setWindowTitle("Matek Screen Companion · Clicky Windows")
        self._response_label.setTextFormat(Qt.TextFormat.PlainText)
        for label in self.findChildren(QLabel):
            if label.text() == "Clicky":
                label.setText("Matek · Clicky")
        self.question = QLabel("")
        self.question.setWordWrap(True)
        self.question.setTextFormat(Qt.TextFormat.PlainText)
        self.layout().insertWidget(2, self.question)
        self.caption_label = QLabel("")
        self.caption_label.setWordWrap(True)
        self.caption_label.setTextFormat(Qt.TextFormat.PlainText)
        self.layout().addWidget(self.caption_label)
        self.entry = QLineEdit()
        self.entry.setStyleSheet("background:#202431;color:#edf0f8;border:1px solid #343d52;border-radius:7px;padding:8px;")
        self.entry.setPlaceholderText("Ask Matek…")
        self.entry.returnPressed.connect(self.submit)
        self.layout().addWidget(self.entry)
        row = QHBoxLayout()
        for label, action in [("Settings", self.settings), ("Copy", self.copy_answer), ("Stop", manager.stop),
                              ("Pause", manager.pause), ("History", self.history), ("Clear", self.clear_memory)]:
            button = QPushButton(label)
            button.setStyleSheet("QPushButton{background:#242938;color:#edf0f8;border:1px solid #343d52;border-radius:6px;padding:5px;}QPushButton:hover{background:#343d52;}")
            button.clicked.connect(lambda _, action=action: action())
            row.addWidget(button)
        self.layout().addLayout(row)
        self.layout().addWidget(QSizeGrip(self))
        self._ptt_btn.pressed.connect(manager.on_hotkey_press)
        self._ptt_btn.released.connect(manager.on_hotkey_release)
        self._ptt_btn.setText("Ask by voice · Ctrl+Win")
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse)
        manager.question_received.connect(self.show_question)
        manager.route_changed.connect(self.show_route)
        manager.local_status.connect(self._status_label.setText)
        manager.caption.connect(self.show_caption)
        manager.sig_response_done.connect(self.answer_done)
        manager.suggestion.connect(self._status_label.setText)
        manager.confirmation.connect(self.confirm)
        manager.speech_cancel.connect(self.cancel_confirmation)
        self.apply()
        self.collapse()

    def apply(self):
        settings = self.manager.settings
        self.setWindowOpacity(settings.opacity)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, settings.always_on_top)
        self._status_label.setText("Listening locally" if settings.microphone else "Ready · microphone off")
        self._badge.setText("Local · " + settings.local_model)

    def _visibility(self, layout, visible):
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget():
                item.widget().setVisible(visible)
            elif item.layout():
                self._visibility(item.layout(), visible)

    def collapse(self):
        if self.manager._answer_busy:
            return
        for index in range(1, self.layout().count()):
            item = self.layout().itemAt(index)
            if item.widget():
                item.widget().hide()
            elif item.layout():
                self._visibility(item.layout(), False)
        self._expanded = False
        bottom = self.y() + self.height()
        self.resize(max(260, self.width()), 56)
        self.move(self.x(), bottom - self.height())

    def expand(self):
        if not self._expanded:
            self._visibility(self.layout(), True)
            self._waveform.hide()
            bottom = self.y() + self.height()
            self.resize(max(430, self.width()), 460)
            self.move(self.x(), max(0, bottom - self.height()))
            self._expanded = True
        self.collapse_timer.stop()

    def enterEvent(self, event):
        self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._full_answer and not self.entry.hasFocus():
            self.collapse_timer.start(1800)
        super().leaveEvent(event)

    def show_question(self, question):
        self.expand()
        self.show()
        self._full_answer = ""
        self.question.setText(question)
        self.caption_label.clear()

    def show_route(self, route):
        self._badge.setText(route.split(" · ")[0])
        self._badge.setToolTip(route)

    def append_response_chunk(self, chunk):
        self.expand()
        self._full_answer += chunk
        super().append_response_chunk(chunk)

    def show_caption(self, text):
        self.caption_label.setText(text[-250:])
        self.caption_label.setVisible(len(self._full_answer.split()) > 50 or "```" in self._full_answer)
        if len(self._full_answer.split()) <= 50 and "```" not in self._full_answer:
            self._response_label.setText(text)

    def answer_done(self, answer):
        self._full_answer = answer
        self.collapse_timer.start(self.manager.settings.answer_display_seconds * 1000)

    def submit(self):
        question = self.entry.text().strip()
        if question:
            self.entry.clear()
            self.entry.clearFocus()
            self.manager.submit_question(question)

    def settings(self):
        if MatekSettingsDialog(self.manager, self).exec() == QDialog.DialogCode.Accepted:
            self.apply()
            self.show()
            self.settings_applied.emit()

    def copy_answer(self):
        QApplication.clipboard().setText(self._full_answer)

    def history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Matek conversations")
        dialog.resize(620, 440)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        messages = list(self.manager._history)
        text.setPlainText("\n\n".join(f"{item.role}: {item.content}" for item in messages))
        layout.addWidget(text)
        delete = QPushButton("Erase saved and session conversations")
        delete.clicked.connect(lambda: (self.manager.store.clear(), self.manager._history.clear(), text.clear()))
        layout.addWidget(delete)
        dialog.exec()

    def clear_memory(self):
        self.manager.stop()
        self.manager._memory.engine.clear()
        self.manager._memory.observer.clear()
        self.manager.local_status.emit("Recent Matek RAM cleared · separate Screenpipe files unchanged")

    def confirm(self, request):
        future = request["future"]
        if future.done() or self.manager._cancel_flag:
            return
        dialog = QMessageBox(self)
        self._confirmation_dialog = dialog
        dialog.setWindowTitle("Authorize paid AI request")
        dialog.setText(f"{request['provider']} · {request['model']}\nQuestion: {request['question']}\n"
                       f"Selected images: {request['images']}\nEstimated reservation: US${request['estimate']:.5f}\n"
                       "Selected conversation/OCR/audio excerpts may also be transmitted. This is separate from a ChatGPT subscription.")
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        approved = dialog.exec() == QMessageBox.StandardButton.Yes
        self._confirmation_dialog = None
        future.get_loop().call_soon_threadsafe(lambda: future.set_result(approved) if not future.done() else None)

    def cancel_confirmation(self):
        dialog = getattr(self, "_confirmation_dialog", None)
        if dialog:
            dialog.reject()

    def showEvent(self, event):
        super().showEvent(event)
        import sys
        if sys.platform == "win32":
            import ctypes
            user = ctypes.windll.user32
            user.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user.SetWindowDisplayAffinity(int(self.winId()), 0x11)
