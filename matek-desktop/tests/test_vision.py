from types import SimpleNamespace
import sys
import pytest
from companion.config import Settings
from companion.vision import ScreenObserver


def capture_fixture(monkeypatch):
    from PIL import Image
    image = Image.new("RGB", (800, 600), "#182c47")
    class Capture:
        monitors = [None, {"left": 0, "top": 0, "width": 800, "height": 600}]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def grab(self, monitor):
            return SimpleNamespace(size=image.size, rgb=image.tobytes())
    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(mss=Capture))
    monkeypatch.setattr("companion.vision.active_window", lambda: ("Unity.exe", "Editor"))
    return image


def test_synthetic_capture_reuses_ocr_and_encoding(monkeypatch):
    capture_fixture(monkeypatch)
    monkeypatch.setattr("companion.vision.PrivacyFilter.monitor_safe", lambda self, monitor: True)
    calls = []
    monkeypatch.setitem(sys.modules, "pytesseract", SimpleNamespace(image_to_string=lambda *a, **k: calls.append(1) or "Error CS1002"))
    observer = ScreenObserver(Settings())
    first = observer.capture()
    second = observer.capture()
    assert first.jpeg is second.jpeg
    assert second.ocr == "Error CS1002"
    assert len(calls) == 1
    assert second.at >= first.at
    assert first.change == 1 and second.change == 0


def test_sensitive_window_blocks_capture(monkeypatch):
    capture_fixture(monkeypatch)
    monkeypatch.setattr("companion.vision.PrivacyFilter.monitor_safe", lambda self, monitor: False)
    with pytest.raises(PermissionError):
        ScreenObserver(Settings()).capture()


def test_privacy_transition_during_capture(monkeypatch):
    capture_fixture(monkeypatch)
    states = iter((True, False))
    monkeypatch.setattr("companion.vision.PrivacyFilter.monitor_safe", lambda self, monitor: next(states))
    with pytest.raises(PermissionError):
        ScreenObserver(Settings()).capture()


def test_disconnected_monitor_and_missing_ocr(monkeypatch):
    capture_fixture(monkeypatch)
    monkeypatch.setattr("companion.vision.PrivacyFilter.monitor_safe", lambda self, monitor: True)
    with pytest.raises(RuntimeError, match="monitor"):
        ScreenObserver(Settings(monitor=2)).capture()
    def failing(*a, **k):
        raise RuntimeError("missing binary")
    monkeypatch.setitem(sys.modules, "pytesseract", SimpleNamespace(image_to_string=failing))
    observer = ScreenObserver(Settings())
    assert observer.capture().jpeg
    assert "OCR unavailable" in observer.ocr_warning
