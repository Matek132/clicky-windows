"""Render only app-owned Qt widgets, never the user's desktop."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from companion.config import Settings
from companion.ui import Overlay, STYLE

app = QApplication([])
app.setStyleSheet(STYLE)
overlay = Overlay(Settings())
overlay.question.setText("Why did that disappear?")
overlay.status.setText("Answer ready · local context → one authorized request")
overlay.append("### A clue in the recent frames\n\nThe selected screenshots show the panel before and after the change. "
               "It may have closed when focus moved to another window.\n\n"
               "**What to check**\n\n1. Reopen the panel from the application's menu.\n2. Check whether it follows the active selection.\n\n"
               "*The snapshots don't show every moment between captures, so I can't confirm the exact cause.*")
overlay.show()
app.processEvents()
target = Path("artifacts/overlay-preview.png")
target.parent.mkdir(exist_ok=True)
overlay.grab().save(str(target.resolve()))
print(target.resolve())
