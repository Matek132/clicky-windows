import base64
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
import httpx
from PIL import Image
import pytest
from memory_backend import LocalMemory, MemorySettings, Evidence, time_window


def test_general_question_never_contacts_screenpipe(monkeypatch):
    def forbidden(request):
        raise AssertionError("Unexpected HTTP request")
    memory = LocalMemory(MemorySettings(enabled=True, screen=True, audio=True), httpx.MockTransport(forbidden))
    assert memory.retrieve("What is quantum entanglement?").backend == "none"


@pytest.mark.parametrize("url", ["https://example.com", "http://192.168.1.2:3030", "http://me:secret@localhost:3030", "http://localhost:3030/redirect"])
def test_reject_remote_endpoint(url):
    with pytest.raises(ValueError):
        LocalMemory(MemorySettings(url=url))


def test_time_units_retention_and_ago():
    now = 2000000
    for unit, seconds in [("seconds", 1), ("minutes", 60), ("hours", 3600), ("days", 86400)]:
        assert time_window(f"What was on screen in the last 2 {unit}?", now, 7) == (now - 2 * seconds, now)
    start, end = time_window("screen ten seconds ago", now, 7)
    assert start <= now - 10 <= end < now
    assert time_window("screen 30 days ago", now, 7)[0] > time_window("screen 30 days ago", now, 7)[1]


def test_ram_expiry_size_and_privacy():
    clock = [1000]
    memory = LocalMemory(MemorySettings(screen=True), clock=lambda: clock[0])
    memory.add(Evidence(995, "screen", "Login to banking"))
    assert not memory.rows
    memory.add(Evidence(995, "screen", "compiler error"))
    assert len(memory.retrieve("what is this error on screen?").records) == 1
    clock[0] += 121
    assert not memory.retrieve("what is on screen?").records


def test_authenticated_bounded_search_and_filtered_image_fetch(monkeypatch):
    monkeypatch.setenv("SCREENPIPE_LOCAL_API_KEY", "test-token")
    now = 2000000
    stamp = datetime.fromtimestamp(now - 5, timezone.utc).isoformat()
    out = BytesIO()
    Image.new("RGB", (32, 32)).save(out, "PNG")
    encoded = base64.b64encode(out.getvalue()).decode()
    calls = []
    def server(request):
        calls.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer test-token"
        if request.url.path == "/search":
            assert request.url.params["include_cloud"] == "false"
            assert request.url.params["include_frames"] == "false"
            assert "start_time" in request.url.params
            return httpx.Response(200, json={"data": [
                {"type": "OCR", "content": {"timestamp": stamp, "text": "password", "frame_id": 1}},
                {"type": "OCR", "content": {"timestamp": stamp, "text": "compiler error", "frame_id": 2}},
                {"type": "Audio", "content": {"timestamp": stamp, "transcription": "A speaker explained the error"}}]})
        return httpx.Response(200, json={"image": encoded})
    memory = LocalMemory(MemorySettings(enabled=True, screen=True, audio=True), httpx.MockTransport(server), lambda: now)
    result = memory.retrieve("what did the speaker say about the error on screen?")
    assert result.backend == "screenpipe" and len(result.records) == 2
    assert len(result.images) == 1
    assert "/frames/1" not in calls
    assert "test-token" not in result.prompt()


def test_unavailable_service_returns_ram_and_requires_auth(monkeypatch):
    monkeypatch.delenv("SCREENPIPE_LOCAL_API_KEY", raising=False)
    memory = LocalMemory(MemorySettings(enabled=True, screen=True), clock=lambda: 1000)
    memory.add(Evidence(995, "screen", "an error"))
    assert not memory.probe()
    assert memory.retrieve("what was on screen?").backend == "ram"


def test_health_only_disables_fallback_when_recorder_is_healthy(monkeypatch):
    monkeypatch.setenv("SCREENPIPE_LOCAL_API_KEY", "token")
    def server(request):
        return httpx.Response(200, json={"status": "healthy", "frame_status": "ok"})
    memory = LocalMemory(MemorySettings(enabled=True), httpx.MockTransport(server))
    assert memory.probe()


def test_redirect_not_followed(monkeypatch):
    monkeypatch.setenv("SCREENPIPE_LOCAL_API_KEY", "token")
    seen = []
    def server(request):
        seen.append(request.url.host)
        return httpx.Response(302, headers={"Location": "https://example.com"})
    memory = LocalMemory(MemorySettings(enabled=True, screen=True), httpx.MockTransport(server))
    assert memory.retrieve("screen history?").backend == "ram"
    assert seen == ["127.0.0.1"]


def test_capture_ownership_and_fallback(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("SCREENPIPE_LOCAL_API_KEY", "token")
    now = [1000]
    healthy = [True]
    def server(request):
        return httpx.Response(200, json={"status": "healthy" if healthy[0] else "error", "frame_status": "ok"})
    memory = LocalMemory(MemorySettings(enabled=True, screen=True), httpx.MockTransport(server), lambda: now[0])
    captures = []
    def capture():
        captures.append(True)
        return [SimpleNamespace(base64_jpeg="sample")]
    memory.poll(capture, lambda: "Editor")
    assert not captures
    healthy[0] = False
    now[0] += 16
    memory.poll(capture, lambda: "Editor")
    assert len(captures) == 1 and len(memory.rows) == 1
    memory.poll(capture, lambda: "Banking login")
    assert len(captures) == 1
