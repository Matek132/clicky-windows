"""Small animated Clicky triangle; no image inference or external assets."""
import math
from PyQt6.QtCore import QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QPolygonF
from PyQt6.QtWidgets import QWidget


class Presence(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(160)

    def advance(self):
        if self.isVisible():
            self.phase += .16
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#a3c4ff"))
        painter.setBrush(QColor(73, 129, 245, int(180 + 40 * math.sin(self.phase))))
        offset = math.sin(self.phase) * 1.3
        painter.drawPolygon(QPolygonF([QPointF(7, 4 + offset), QPointF(23, 16 + offset), QPointF(14, 17 + offset), QPointF(10, 25 + offset)]))
