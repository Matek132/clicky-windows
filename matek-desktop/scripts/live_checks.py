"""Explicit local hardware checks. Capture/audio stay in RAM; reports contain test data and metrics only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import threading
import time
import wave
from dataclasses import replace
import numpy as np
import pyaudiowpatch as pa
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt, QTimer
from companion.config import Settings
from companion.vision import ScreenObserver
from companion.audio import Transcriber, AudioService

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "artifacts" / "live-checks.json"


def microphone_check(report):
    with pa.PyAudio() as audio:
        cfg = Settings.load()
        device = audio.get_default_input_device_info() if cfg.mic_device < 0 else audio.get_device_info_by_index(cfg.mic_device)
        rate, channels = int(device["defaultSampleRate"]), int(device["maxInputChannels"])
        with audio.open(format=pa.paInt16, channels=channels, rate=rate, input=True,
                        input_device_index=int(device["index"]), frames_per_buffer=int(rate * .03)) as stream:
            samples = np.frombuffer(stream.read(rate, exception_on_overflow=False), dtype=np.int16)
            report["microphone"] = {"device": device["name"], "samples_read": len(samples),
                                    "rms": float(np.sqrt(np.mean(samples.astype(float) ** 2))), "stream_opened": True}


def loopback_check(report):
    cfg = replace(Settings.load(), microphone=False, system_audio=True, activation="push", cloud_access=False)
    transcripts, statuses = [], []
    service = AudioService(cfg, transcripts.append, statuses.append)
    service.start()
    time.sleep(1)
    fixture = ROOT / "tests" / "fixtures" / "question.wav"
    with wave.open(str(fixture), "rb") as recording, pa.PyAudio() as audio:
        pcm = recording.readframes(recording.getnframes())
        # Send deterministic spoken test audio to the selected output's physical analogue.
        loopback = audio.get_default_wasapi_loopback() if cfg.system_device < 0 else audio.get_device_info_by_index(cfg.system_device)
        output = audio.get_default_output_device_info()
        # Default speaker and default WASAPI loopback normally refer to the same endpoint.
        rate, channels = int(output["defaultSampleRate"]), int(output["maxOutputChannels"])
        samples = np.frombuffer(pcm, dtype=np.int16)
        count = int(len(samples) * rate / 16000)
        resampled = np.interp(np.arange(count) * 16000 / rate, np.arange(len(samples)), samples).astype(np.int16)
        interleaved = np.repeat(resampled[:, None], channels, axis=1).tobytes()
        with audio.open(format=pa.paInt16, channels=channels, rate=rate, output=True,
                        output_device_index=int(output["index"])) as stream:
            stream.write(interleaved)
            stream.write(b"\0" * rate * channels * 2)
    until = time.monotonic() + 25
    while time.monotonic() < until and not any("what" in t.text.lower() and "mean" in t.text.lower() for t in transcripts):
        time.sleep(.2)
    service.close()
    for thread in service.threads:
        thread.join(timeout=3)
    recognized = next((t for t in transcripts if "what" in t.text.lower() and "mean" in t.text.lower()), None)
    report["loopback"] = {"device": loopback["name"], "source": recognized.source if recognized else None,
                          "recognized_test_question": bool(recognized),
                          "last_status": statuses[-1] if statuses else None}


def screen_check(report):
    app = QApplication([])
    cfg = Settings.load()
    card = QLabel("MATEK CAPTURE TEST\n\nERROR CS1002\n\nWhat does this symbol mean?\n\n2 + 2 = 4")
    card.setWindowTitle("Matek Hardware Test")
    card.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    card.setAlignment(Qt.AlignCenter)
    card.setStyleSheet("background:white;color:black;font:48px 'Segoe UI';")
    screen = app.screens()[min(cfg.monitor - 1, len(app.screens()) - 1)]
    card.setGeometry(screen.geometry())
    card.showFullScreen()
    card.raise_()
    card.activateWindow()
    def capture():
        try:
            observer = ScreenObserver(cfg)
            frame = observer.capture(fresh=True)
            report["screen"] = {"capture_ok": bool(frame.jpeg), "ocr_test_text_found": "MATEK CAPTURE TEST" in frame.ocr,
                                "ocr_error_code_found": "CS1002" in frame.ocr, "jpeg_bytes": len(frame.jpeg),
                                "ocr_warning": observer.ocr_warning,
                                "foreground_was_testcard": frame.title == "Matek Hardware Test"}
            # Persist ONLY the generated test card cropped out of app-owned widget rendering.
            card.grab().save(str(ROOT / "artifacts" / "test-card.png"))
            observer.clear()
        except Exception as exc:
            report["screen"] = {"error_type": type(exc).__name__}
        finally:
            card.close()
            app.quit()
    QTimer.singleShot(900, capture)
    app.exec()


if __name__ == "__main__":
    report = {"cloud_requests": 0}
    try:
        microphone_check(report)
    except Exception as exc:
        report["microphone"] = {"error_type": type(exc).__name__}
    if "--screen-only" not in sys.argv:
        loopback_check(report)
    screen_check(report)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
