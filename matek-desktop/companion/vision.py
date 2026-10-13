from io import BytesIO
import time
import numpy as np
from PIL import Image
from .context import Frame
from .security import PrivacyFilter, active_window


class ScreenObserver:
    def __init__(self, settings):
        self.settings = settings
        self.previous = None
        self.unchanged = 0
        self.ocr_warning = ""
        self.cached = None

    def clear(self):
        self.cached = None
        self.previous = None
        self.unchanged = 0

    def expire(self):
        if self.cached and time.time() - self.cached.at > self.settings.retention_seconds:
            self.clear()

    def capture(self, fresh=False):
        import mss
        cfg = self.settings
        captured_at = time.time()
        with mss.mss() as capture:
            if cfg.monitor >= len(capture.monitors):
                raise RuntimeError("Selected monitor is disconnected. Select an available monitor in Settings.")
            monitor = capture.monitors[cfg.monitor]
            privacy = PrivacyFilter(cfg.exclusions)
            app, title = active_window()
            if privacy.excluded(app, title) or not privacy.monitor_safe(monitor):
                self.previous = None
                raise PermissionError("Screen capture skipped: an excluded window is visible, or privacy inspection failed.")
            raw = capture.grab(monitor)
            # Recheck after capture; never retain a frame if visibility changed during capture.
            if not privacy.monitor_safe(monitor):
                raise PermissionError("Screen capture skipped: privacy state changed during capture.")
            image = Image.frombytes("RGB", raw.size, raw.rgb)
        image.thumbnail((cfg.image_max_side, cfg.image_max_side))
        small = np.asarray(image.resize((64, 36)).convert("L"), dtype=np.float32)
        change = 1.0 if self.previous is None else float(np.mean(np.abs(small - self.previous)) / 255)
        self.previous = small
        self.unchanged = self.unchanged + 1 if change < 0.015 else 0
        if self.unchanged and self.cached and self.cached.app == app and self.cached.title == title:
            # Reuse encoded image and OCR, but refresh timestamp so an unchanged desktop does not expire.
            return Frame(captured_at, self.cached.jpeg, app, title, self.cached.ocr, change)
        text = ""
        if cfg.ocr:
            try:
                import pytesseract
                if cfg.tesseract_path:
                    pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_path
                text = pytesseract.image_to_string(image, timeout=4)[:6000]
                self.ocr_warning = ""
            except Exception:
                self.ocr_warning = "OCR unavailable. Install Tesseract or configure its path; screenshots still work."
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=78)
        self.cached = Frame(captured_at, buffer.getvalue(), app, title, text, change)
        return self.cached

    def delay(self):
        base = self.settings.capture_seconds
        if self.settings.preset == "gaming":
            base = max(base, 10)
        return base * min(4, 1 + self.unchanged // 3)
