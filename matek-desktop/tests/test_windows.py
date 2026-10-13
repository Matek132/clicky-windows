"""Read-only Windows integration checks: no capture and no real credentials."""
import sys
import pytest
from companion.security import active_window
from companion.hotkeys import Hotkeys


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_active_window_metadata():
    app, title = active_window()
    assert isinstance(app, str)
    assert isinstance(title, str)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_hotkey_registration_lifecycle():
    # Register an uncommon temporary chord, never inject a keyboard event.
    notices = []
    hotkeys = Hotkeys({"test": "Ctrl+Alt+Shift+F24"}, lambda event: None, notices.append)
    hotkeys.start()
    hotkeys.close()
    assert not hotkeys.thread.is_alive()
