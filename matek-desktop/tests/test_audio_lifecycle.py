import sys
import threading
import time
from types import SimpleNamespace
from companion.audio import audio_manager


def test_portaudio_lifecycle_is_serialized(monkeypatch):
    active = []
    errors = []
    class Manager:
        def __init__(self):
            if active:
                errors.append("concurrent initialization")
            active.append(1)
            time.sleep(.01)
            active.pop()
        def terminate(self):
            if active:
                errors.append("concurrent termination")
            active.append(1)
            time.sleep(.01)
            active.pop()
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", SimpleNamespace(PyAudio=Manager))
    barrier = threading.Barrier(4)
    def run():
        barrier.wait()
        with audio_manager():
            time.sleep(.01)
    workers = [threading.Thread(target=run) for _ in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert errors == []
