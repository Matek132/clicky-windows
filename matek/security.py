import ctypes
from ctypes import wintypes
import sys


def windows_api():
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    return user


class Credentials:
    @staticmethod
    def get(endpoint):
        import keyring
        return keyring.get_password("MatekScreenCompanion", endpoint)

    @staticmethod
    def set(endpoint, value):
        import keyring
        if value:
            keyring.set_password("MatekScreenCompanion", endpoint, value)
        else:
            try:
                keyring.delete_password("MatekScreenCompanion", endpoint)
            except keyring.errors.PasswordDeleteError:
                pass


def window_info(hwnd):
    import psutil
    user = windows_api()
    n = user.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(n + 1)
    user.GetWindowTextW(hwnd, title, n + 1)
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        app = psutil.Process(pid.value).name()
    except (psutil.Error, ValueError):
        app = "unknown"
    return app, title.value


def active_window():
    if sys.platform != "win32":
        return "unknown", "unknown"
    user = windows_api()
    return window_info(user.GetForegroundWindow())


class PrivacyFilter:
    def __init__(self, exclusions):
        self.terms = [s.strip().casefold() for s in exclusions.split(",") if s.strip()]
        self.terms.extend(["api keys", "matek settings", "credentials", ".env"])

    def excluded(self, app, title):
        text = f"{app} {title}".casefold()
        return any(term in text for term in self.terms)

    def monitor_safe(self, monitor):
        """Block the whole frame if any excluded visible window overlaps the monitor."""
        if sys.platform != "win32":
            return False
        user = windows_api()
        blocked = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def inspect(hwnd, _):
            try:
                if user.IsWindowVisible(hwnd) and not user.IsIconic(hwnd):
                    rect = wintypes.RECT()
                    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
                        blocked.append(True)
                        return True
                    intersects = (rect.left < monitor["left"] + monitor["width"] and rect.right > monitor["left"]
                                  and rect.top < monitor["top"] + monitor["height"] and rect.bottom > monitor["top"])
                    if intersects and self.excluded(*window_info(hwnd)):
                        blocked.append(True)
            except Exception:
                blocked.append(True)
            return True

        if not user.EnumWindows(callback_type(inspect), 0):
            return False
        return not blocked
