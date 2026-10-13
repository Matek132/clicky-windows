"""One-minute real capture/UI soak. No screenshots, transcripts or ambient recordings are persisted."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
import tempfile
import json
import time
import socket
from dataclasses import replace
import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from companion.config import Settings
from companion.app import Companion

cfg = replace(Settings.load(), mode="local", cloud_access=False, activation="push", system_questions=False,
              persistent_history=False, microphone=True, system_audio=True, continuous_screen=True,
              launch_minimized=True)
network_attempts = []
def blocked(*args, **kwargs):
    network_attempts.append(1)
    raise AssertionError("Background capture attempted networking")
socket.socket.connect = blocked
process = psutil.Process()
started = time.monotonic()
cpu_start = process.cpu_times()
report = {}
with tempfile.TemporaryDirectory(prefix="matek-idle-") as directory:
    os.environ["LOCALAPPDATA"] = directory
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    companion = Companion(app, cfg, runtime_hooks=False)
    def finish():
        cpu_end = process.cpu_times()
        seconds = time.monotonic() - started
        report.update({"seconds": round(seconds, 2), "rss_mb": round(process.memory_info().rss / 1024**2, 2),
                       "cpu_percent_one_core": round(((cpu_end.user + cpu_end.system) - (cpu_start.user + cpu_start.system)) / seconds * 100, 2),
                       "network_attempts": len(network_attempts), "cloud_ledger_entries": len(companion.ledger.history()),
                       "context_counts": companion.engine.inspect(), "busy": companion.busy})
        app.quit()
    QTimer.singleShot(60000, finish)
    app.exec()
Path("artifacts/idle-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
