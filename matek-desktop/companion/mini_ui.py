"""Small code-drawn desktop mascot, hover composer and temporary answer bubble."""
import ctypes
import math
import sys
from PySide6.QtCore import Qt, QTimer, QRectF, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QRegion, QCursor
from PySide6.QtWidgets import (QApplication, QWidget, QLineEdit, QPushButton, QTextBrowser, QLabel)
from PySide6.QtCore import Signal
from .ui import icon


class Mascot(QWidget):
    clicked = Signal()
    dragged = Signal(QPoint)

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(82, 86)
        self.setStyleSheet("background:transparent;")
        self.phase = 0.0
        self.mode = "ready"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(50)

    def animate(self):
        if self.window().isVisible():
            self.phase += .12
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bob = math.sin(self.phase) * 2
        color = {"ready": "#79d6bc", "listening": "#77dbea", "thinking": "#b9a6ef",
                 "speaking": "#a9e7ad", "paused": "#8792a2"}.get(self.mode, "#79d6bc")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(16, 73, 52, 7))
        for radius, alpha in ((37, 18), (33, 28)):
            p.setBrush(QColor(121, 214, 188, alpha))
            p.drawEllipse(QRectF(41 - radius, 40 + bob - radius, radius * 2, radius * 2))
        p.setBrush(QColor("#132332"))
        p.setPen(QPen(QColor(color), 2.3))
        p.drawRoundedRect(QRectF(13, 13 + bob, 56, 54), 23, 23)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        blink = math.sin(self.phase * .24) > .993
        for x in (29, 51):
            p.drawRoundedRect(QRectF(x - 3, 32 + bob, 6, 2 if blink or self.mode == "paused" else 9), 3, 3)
        p.setPen(QPen(QColor(color), 2))
        if self.mode == "speaking":
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(36, 49 + bob, 9, 3 + abs(math.sin(self.phase * 3)) * 5))
        else:
            p.drawArc(QRectF(31, 44 + bob, 20, 11), 195 * 16, 150 * 16)
        if self.mode == "thinking":
            p.drawArc(QRectF(6, 6 + bob, 70, 68), int(self.phase * 90) * 16, 70 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF(61, 62 + bob, 6, 6))
        p.end()

    def mousePressEvent(self, event):
        self.start = event.globalPosition().toPoint()
        self.origin = self.window().pos()
        self.moved = False

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, "start"):
            difference = event.globalPosition().toPoint() - self.start
            if difference.manhattanLength() > 5:
                self.moved = True
                self.window().move(self.origin + difference)

    def mouseReleaseEvent(self, event):
        if not getattr(self, "moved", False):
            self.clicked.emit()


class MiniOverlay(QWidget):
    ask = Signal(str)
    action = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.answer = ""
        self.collapsed = True
        self.setWindowTitle("Matek Screen Companion")
        self.setWindowIcon(icon())
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet("MiniOverlay { background:transparent; }")
        self.setFixedSize(430, 310)
        self.mascot = Mascot(self)
        self.mascot.move(346, 222)
        self.mascot.clicked.connect(lambda: self.action.emit("stop_voice"))
        self.controls = QWidget(self)
        self.controls.setGeometry(4, 235, 338, 51)
        self.controls.setStyleSheet("background:#162637;border:1px solid #3d576c;border-radius:12px;")
        self.entry = QLineEdit(self.controls)
        self.entry.setGeometry(8, 8, 196, 34)
        self.entry.setPlaceholderText("Ask Matek…")
        self.entry.setMaxLength(12000)
        self.entry.returnPressed.connect(self.submit)
        self.submit_button = QPushButton("↵", self.controls)
        self.submit_button.setGeometry(207, 8, 32, 34)
        self.submit_button.clicked.connect(self.submit)
        settings_button = QPushButton("⚙", self.controls)
        settings_button.setToolTip("Settings")
        settings_button.setGeometry(241, 8, 36, 34)
        settings_button.clicked.connect(lambda: self.action.emit("settings"))
        pause_button = QPushButton("Ⅱ", self.controls)
        pause_button.setToolTip("Pause / resume microphone and screen capture")
        pause_button.setGeometry(281, 8, 36, 34)
        pause_button.clicked.connect(lambda: self.action.emit("pause"))
        self.cancel_button = self.submit_button
        self.body = QWidget(self)
        self.body.setGeometry(4, 4, 416, 214)
        self.body.setStyleSheet("background:#142334;border:1px solid #3d576c;border-radius:15px;")
        self.question = QLabel(self.body)
        self.question.setGeometry(14, 10, 370, 36)
        self.question.setTextFormat(Qt.PlainText)
        self.question.setWordWrap(True)
        self.question.setStyleSheet("border:0;color:#95aec0;font-size:11px;")
        self.browser = QTextBrowser(self.body)
        self.browser.setGeometry(12, 50, 390, 147)
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet("border:0;background:transparent;font-size:15px;color:#f1f7fc;")
        dismiss = QPushButton("×", self.body)
        dismiss.setGeometry(384, 6, 25, 27)
        dismiss.setStyleSheet("border:0;padding:0;background:transparent;")
        dismiss.clicked.connect(self.dismiss)
        self.status = QLabel(self)
        self.status.hide()
        self.permissions = QLabel(self)
        self.permissions.hide()
        self.body.hide()
        self.controls.hide()
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.update_hover)
        self.hover_timer.start(120)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.dismiss)
        self.apply(settings)
        self.update_mask()

    def paintEvent(self, event):
        pass  # Only painted child regions are visible / receive input.

    def update_mask(self):
        region = QRegion(self.mascot.geometry().adjusted(-3, -3, 0, 0))
        if not self.controls.isHidden():
            region |= QRegion(0, 222, 430, 86)
        if not self.body.isHidden():
            region |= QRegion(self.body.geometry())
        self.setMask(region)

    def update_hover(self):
        if not self.isVisible():
            return
        position = self.mapFromGlobal(QCursor.pos())
        hovered = self.mascot.geometry().contains(position) or (not self.controls.isHidden() and self.controls.geometry().contains(position))
        focused = self.entry.hasFocus()
        show = hovered or focused
        if show != (not self.controls.isHidden()):
            self.controls.setVisible(show)
            self.update_mask()

    def submit(self):
        text = self.entry.text().strip()
        if text:
            self.ask.emit(text)
            self.entry.clearFocus()

    def apply(self, settings):
        self.settings = settings
        self.setWindowOpacity(settings.opacity)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, settings.always_on_top)
        # Hover interaction needs the mascot to receive mouse events.
        self.setWindowFlag(Qt.WindowTransparentForInput, False)
        self.permissions.setText(" · ".join(f"{name} {'on' if enabled else 'off'}" for name, enabled in
                                (("Mic", settings.microphone), ("System", settings.system_audio),
                                 ("Screen", settings.continuous_screen), ("Cloud", settings.cloud_access))))
        self.mascot.setToolTip(self.permissions.text())

    def position_default(self):
        screens = QApplication.screens()
        area = screens[min(self.settings.monitor - 1, len(screens) - 1)].availableGeometry()
        x, y = self.settings.overlay_x, self.settings.overlay_y
        # The old panel coordinates remain bounded; only the small mascot is visible while idle.
        if x < 0 or not any(s.availableGeometry().contains(QPoint(x, y)) for s in screens):
            x, y = area.right() - self.width() - 18, area.bottom() - self.height() - 18
        x = min(max(area.left(), x), area.right() - self.width())
        y = min(max(area.top(), y), area.bottom() - self.height())
        self.move(x, y)

    def reveal(self, focus=False):
        self.show()
        if sys.platform == "win32":
            user = ctypes.windll.user32
            user.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user.SetWindowDisplayAffinity(int(self.winId()), 0x11)
        if focus:
            self.controls.show()
            self.activateWindow()
            self.entry.setFocus()
        self.update_mask()

    def begin(self, question):
        self.answer = ""
        self.question.setText(question[:180])
        self.entry.clear()
        self.browser.setPlainText("…")
        self.body.show()
        self.hide_timer.stop()
        self.mascot.mode = "thinking"
        self.reveal()

    def append(self, chunk):
        self.answer += chunk

    def show_words(self, text):
        self.browser.setPlainText(text)
        self.fit_bubble()
        self.body.show()
        self.hide_timer.stop()
        self.reveal()
        bar = self.browser.verticalScrollBar()
        bar.setValue(bar.maximum())

    def preview_question(self, text):
        self.question.setText(text[-180:])
        self.browser.setPlainText("Listening…")
        self.fit_bubble()
        self.body.show()
        self.reveal()

    def fit_bubble(self):
        self.browser.document().setTextWidth(self.browser.viewport().width())
        height = min(146, max(44, int(self.browser.document().size().height()) + 10))
        self.body.setGeometry(4, 214 - (height + 62), 416, height + 62)
        self.browser.setGeometry(12, 50, 390, height)
        self.update_mask()

    def set_mode(self, mode, status=""):
        self.mascot.mode = mode
        if status:
            self.mascot.setToolTip(status + "\n" + self.permissions.text())
        self.mascot.update()

    def finish_presentation(self):
        self.hide_timer.start(self.settings.answer_display_seconds * 1000)

    def dismiss(self):
        self.body.hide()
        self.hide_timer.stop()
        self.update_mask()

    def collapse(self):
        self.dismiss()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
