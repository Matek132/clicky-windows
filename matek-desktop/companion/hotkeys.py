import ctypes
from ctypes import wintypes
import sys
import threading


def parse_hotkey(value):
    parts = value.upper().split("+")
    mods = 0x4000  # MOD_NOREPEAT
    codes = {"ALT": 1, "CTRL": 2, "SHIFT": 4, "WIN": 8}
    for part in parts[:-1]:
        if part not in codes:
            raise ValueError("Hotkey modifiers: Ctrl, Alt, Shift, Win")
        mods |= codes[part]
    key = parts[-1]
    names = {"SPACE": 0x20, "BACKSPACE": 0x08, "ESC": 0x1B, "ENTER": 0x0D}
    if key in names:
        vk = names[key]
    elif len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError("Hotkey key must be a letter, digit, F1–F24, Space, Backspace, Esc or Enter")
    return mods, vk


class Hotkeys:
    def __init__(self, mapping, emit, status):
        self.mapping = mapping
        self.emit = emit
        self.status = status
        self.thread_id = None
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name="global-hotkeys")

    def start(self):
        if sys.platform == "win32":
            self.thread.start()

    def run(self):
        user = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # create thread queue
        registered = {}
        try:
            for identity, (action, shortcut) in enumerate(self.mapping.items(), 1):
                try:
                    mods, key = parse_hotkey(shortcut)
                    if not user.RegisterHotKey(None, identity, mods, key):
                        raise ValueError("Shortcut already in use")
                    registered[identity] = action
                except ValueError:
                    self.status(f"Hotkey unavailable: {shortcut} · change it in Settings")
            while not self.stopping.is_set() and user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312 and msg.wParam in registered:
                    self.emit(registered[msg.wParam])
        finally:
            for identity in registered:
                user.UnregisterHotKey(None, identity)

    def close(self):
        self.stopping.set()
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if self.thread.is_alive():
            self.thread.join(timeout=1)
