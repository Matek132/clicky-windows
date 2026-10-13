import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from memory_backend import LocalMemory, MemorySettings
from ui.memory_dialog import MemoryDialog


def test_memory_settings_save_and_reload(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    memory = LocalMemory(MemorySettings())
    dialog = MemoryDialog(memory)
    dialog.screen.setChecked(True)
    dialog.days.setValue(3)
    dialog.save()
    assert memory.settings.screen and memory.settings.retention_days == 3
    assert MemorySettings.from_env().retention_days == 3
    assert not memory.settings.enabled
    dialog.close()
