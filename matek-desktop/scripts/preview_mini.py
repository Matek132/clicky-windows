"""Render app-owned miniature UI only; no desktop capture or sound."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from companion.config import Settings
from companion.mini_ui import MiniOverlay
from companion.ui import STYLE

app = QApplication([])
app.setStyleSheet(STYLE)
overlay = MiniOverlay(Settings())
overlay.reveal()
app.processEvents()
overlay.mascot.grab().save("artifacts/mascot-preview.png")
overlay.controls.show()
overlay.begin("How do I craft a lantern in Minecraft?")
overlay.show_words("Put one torch in the centre of a crafting table and surround it with eight iron nuggets.")
overlay.set_mode("speaking")
app.processEvents()
overlay.controls.show()
overlay.update_mask()
overlay.grab().save("artifacts/mini-preview.png")
print(Path("artifacts/mini-preview.png").resolve())
