from dataclasses import replace
from pathlib import Path
import threading
import json
import pytest
import httpx

from companion.config import Settings
from companion.context import ContextEngine, Frame, Transcript, Package
from companion.detection import QuestionDetector
from companion.costs import CostLedger
from companion.controller import RequestController
from companion.providers import OpenAIProvider, OllamaProvider, response_payload, Cancelled
from companion.security import PrivacyFilter
from companion.hotkeys import parse_hotkey


@pytest.fixture
def clock():
    return [1000.0]


@pytest.fixture
def setup(tmp_path, clock):
    cfg = Settings(mode="hybrid", cloud_access=True, manual_screenshots=True, microphone=True)
    ledger = CostLedger(tmp_path / "usage.db", Path("config/pricing.json"), lambda: clock[0])
    engine = ContextEngine(cfg, lambda: clock[0])
    controller = RequestController(ledger, lambda: clock[0])
    return cfg, ledger, engine, controller


class FakeProvider:
    def __init__(self):
        self.calls = []

    def stream(self, package, settings, cancel, on_chunk):
        self.calls.append(package)
        on_chunk("A useful answer")
        return (100, 20)


def test_eight_hour_idle_has_zero_provider_calls(setup, clock):
    cfg, ledger, engine, controller = setup
    cfg.activation = "push"
    detector = QuestionDetector(cfg, lambda: clock[0])
    provider = FakeProvider()
    for _ in range(8 * 60 * 12):
        clock[0] += 5
        engine.add_frame(Frame(clock[0], b"image", "game.exe", "Minecraft"))
        engine.add_transcript(Transcript(clock[0], "What is that?", "system"))
        assert detector.detect("What is that?", "system") is None
        engine.purge()
    assert not provider.calls
    assert not ledger.history()
    assert engine.inspect()["frames"] <= cfg.max_frames
    assert engine.inspect()["transcripts"] <= 100


def test_temporal_selection_before_after(setup):
    cfg, _, engine, _ = setup
    engine.add_frame(Frame(970, b"before", "game", "game", change=0.01))
    engine.add_frame(Frame(975, b"after", "game", "game", change=0.9))
    engine.add_frame(Frame(999, b"now", "game", "game", change=0.02))
    assert [f.jpeg for f in engine.select("Why did that disappear?").frames] == [b"before", b"after", b"now"]
    cfg.max_request_images = 2
    assert [f.jpeg for f in engine.select("What changed?").frames] == [b"before", b"now"]
    cfg.max_request_images = 1
    assert len(engine.select("What changed?").frames) == 1


def test_ordinary_question_only_latest(setup):
    _, _, engine, _ = setup
    for at in (980, 990, 999):
        engine.add_frame(Frame(at, b"image", "Unity", "Editor"))
    assert [f.at for f in engine.select("What is this symbol?").frames] == [999]


def test_expiry_memory_and_privacy(setup, clock):
    cfg, _, engine, _ = setup
    engine.add_frame(Frame(800, b"expired", "game", "game"))
    engine.add_frame(Frame(995, b"secret", "Bitwarden", "vault"))
    engine.add_frame(Frame(996, b"safe", "Unity", "Editor"))
    assert [f.jpeg for f in engine.select("what?").frames] == [b"safe"]
    cfg.exclusions += ",Unity"
    assert not engine.select("what?").frames
    cfg.exclusions = ""
    cfg.manual_screenshots = False
    assert not engine.select("what?").frames
    cfg.manual_screenshots = True
    clock[0] += 121
    assert not engine.select("what?").frames


def test_byte_bound(setup):
    cfg, _, engine, _ = setup
    cfg.screen_memory_mb = 4
    for at in range(980, 1000):
        engine.add_frame(Frame(at, b"x" * 1000000, "game", "game"))
    assert engine.inspect()["jpeg_bytes"] <= 4 * 1024 * 1024


def test_multimodal_payload_and_followup(setup):
    cfg, _, engine, _ = setup
    engine.add_frame(Frame(999, b"jpeg", "Unity", "Error", "Compiler error"))
    engine.add_turn("What is this?", "An error")
    payload = response_payload(engine.select("How do I fix this?", "microphone"), cfg)
    assert payload["store"] is False
    assert payload["stream"] is True
    assert payload["input"][0] == {"role": "user", "content": "What is this?"}
    content = payload["input"][-1]["content"]
    assert any(c["type"] == "input_image" for c in content)
    assert "How do I fix this?" in content[0]["text"]
    assert "Compiler error" in content[0]["text"]


def test_audio_source_permissions_and_relevance(setup):
    cfg, _, engine, controller = setup
    engine.add_transcript(Transcript(995, "The lecturer explains consciousness", "system"))
    engine.add_transcript(Transcript(997, "What does that mean?", "microphone"))
    assert all(t.source == "microphone" for t in engine.select("speaker consciousness").transcripts)
    cfg.system_audio = True
    assert any(t.source == "system" for t in engine.select("speaker consciousness").transcripts)
    with pytest.raises(PermissionError):
        controller.prepare(engine.select("what?", "system"), cfg)
    cfg.microphone = False
    with pytest.raises(PermissionError):
        controller.prepare(engine.select("what?", "microphone"), cfg)


def test_cloud_permission_and_confirmation(setup):
    cfg, ledger, engine, controller = setup
    cfg.cloud_access = False
    with pytest.raises(PermissionError):
        controller.prepare(engine.select("what?"), cfg)
    assert ledger.history() == []
    cfg.cloud_access = True
    cfg.mode = "confirm"
    prepared = controller.prepare(engine.select("what?"), replace(cfg))
    provider = FakeProvider()
    with pytest.raises(PermissionError):
        controller.execute(prepared, provider, threading.Event(), lambda x: None)
    assert not provider.calls
    assert not ledger.history()
    controller.execute(prepared, provider, threading.Event(), lambda x: None, approved=True)
    assert len(provider.calls) == 1
    assert ledger.history()[0][4] == "completed"


@pytest.mark.parametrize("limit", ["daily_usd", "monthly_usd", "per_question_usd"])
def test_budget_rejection(setup, limit):
    cfg, ledger, engine, controller = setup
    setattr(cfg, limit, 0)
    with pytest.raises(PermissionError):
        controller.prepare(engine.select("what?"), cfg)
    assert not ledger.history()


def test_budget_recheck_after_prepare(setup):
    cfg, ledger, engine, controller = setup
    prepared = controller.prepare(engine.select("question?"), cfg)
    cfg.daily_usd = prepared.estimate * 1.5
    ledger.reserve(prepared.estimate, cfg)
    provider = FakeProvider()
    with pytest.raises(PermissionError):
        controller.execute(prepared, provider, threading.Event(), lambda x: None)
    assert not provider.calls


def test_duplicate_and_replay(setup, clock):
    cfg, _, engine, controller = setup
    prepared = controller.prepare(engine.select("what?"), cfg)
    provider = FakeProvider()
    controller.execute(prepared, provider, threading.Event(), lambda x: None)
    with pytest.raises(PermissionError):
        controller.execute(controller.prepare(engine.select("WHAT?"), cfg), provider, threading.Event(), lambda x: None)
    clock[0] += 20
    with pytest.raises(PermissionError):
        controller.execute(prepared, provider, threading.Event(), lambda x: None)
    assert len(provider.calls) == 1


def test_cancel_before_send_and_failed_reservation(setup):
    cfg, ledger, engine, controller = setup
    prepared = controller.prepare(engine.select("what?"), cfg)
    cancel = threading.Event()
    cancel.set()
    provider = FakeProvider()
    with pytest.raises(Cancelled):
        controller.execute(prepared, provider, cancel, lambda x: None)
    assert not ledger.history()
    class Broken:
        def stream(self, *args):
            raise RuntimeError("connection lost")
    with pytest.raises(RuntimeError):
        controller.execute(prepared, Broken(), threading.Event(), lambda x: None)
    assert ledger.history()[0][2] == ledger.history()[0][3]


def test_local_mode_bypasses_cloud_and_costs(setup):
    cfg, ledger, engine, controller = setup
    cfg.mode = "local"
    cfg.cloud_access = False
    prepared = controller.prepare(engine.select("what?"), cfg)
    provider = FakeProvider()
    controller.execute(prepared, provider, threading.Event(), lambda x: None)
    assert len(provider.calls) == 1
    assert not ledger.history()


def test_unknown_pricing_blocks_cloud(setup):
    cfg, _, engine, controller = setup
    cfg.model = "unknown-model"
    with pytest.raises(ValueError, match="pricing"):
        controller.prepare(engine.select("what?"), cfg)


def test_streaming_transport_single_request(setup):
    cfg, _, engine, _ = setup
    calls = []
    def handle(request):
        calls.append(request)
        data = json.loads(request.content)
        assert data["stream"]
        assert request.headers["authorization"] == "Bearer fake-test-key"
        return httpx.Response(200, text='data: {"type":"response.output_text.delta","delta":"Hello"}\n\n'
                              'data: {"type":"response.completed","response":{"usage":{"input_tokens":123,"output_tokens":4}}}\n\n')
    chunks = []
    usage = OpenAIProvider("fake-test-key", httpx.MockTransport(handle)).stream(engine.select("what?"), cfg, threading.Event(), chunks.append)
    assert usage == (123, 4)
    assert chunks == ["Hello"]
    assert len(calls) == 1


def test_stream_network_failure_has_no_retry(setup):
    cfg, _, engine, _ = setup
    calls = []
    def handle(request):
        calls.append(request)
        raise httpx.ConnectError("offline")
    with pytest.raises(httpx.ConnectError):
        OpenAIProvider("fake", httpx.MockTransport(handle)).stream(engine.select("what?"), cfg, threading.Event(), lambda x: None)
    assert len(calls) == 1


def test_ollama_text_only_is_explicit(setup):
    cfg, _, engine, _ = setup
    def handle(request):
        assert request.url.host == "127.0.0.1"
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details": {"parameter_size": "3B"}})
        data = json.loads(request.content)
        assert not data["messages"][-1]["images"]
        assert "text-only" in data["messages"][-1]["content"]
        return httpx.Response(200, text='{"message":{"content":"Local answer"},"done":true}\n')
    chunks = []
    OllamaProvider(httpx.MockTransport(handle)).stream(engine.select("what?"), cfg, threading.Event(), chunks.append)
    assert chunks == ["Local answer"]


def test_ollama_remote_forwarding_is_blocked(setup):
    cfg, _, engine, _ = setup
    requests = []
    def handle(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={"remote_model": "some-cloud-model", "remote_host": "https://ollama.com"})
    with pytest.raises(PermissionError, match="cloud service"):
        OllamaProvider(httpx.MockTransport(handle)).stream(engine.select("what?"), cfg, threading.Event(), lambda x: None)
    assert requests == ["/api/show"]
    cfg.local_model = "gemma:cloud"
    with pytest.raises(PermissionError, match="Cloud-hosted"):
        OllamaProvider(httpx.MockTransport(handle)).stream(engine.select("what?"), cfg, threading.Event(), lambda x: None)
    assert requests == ["/api/show"]


def test_wake_automatic_and_debounce(clock):
    cfg = Settings(activation="wake")
    detector = QuestionDetector(cfg, lambda: clock[0])
    assert detector.detect("Why is that?", "microphone") is None
    assert detector.detect("Matek, explain this", "microphone") == "explain this"
    assert detector.detect("Matek, what is that?", "microphone") is None
    clock[0] += 10
    assert detector.detect("Matek, what is that?", "system") is None
    cfg.activation = "automatic"
    assert detector.detect("What does this mean?", "microphone", confidence=0.1) is None
    assert detector.detect("What does this mean?", "microphone") == "What does this mean?"


def test_settings_roundtrip_and_loopback_validation(tmp_path):
    cfg = Settings()
    cfg.save(tmp_path / "settings.json")
    assert Settings.load(tmp_path / "settings.json") == cfg
    cfg.local_url = "http://some-remote-server:11434"
    with pytest.raises(ValueError, match="loopback"):
        cfg.validate()


def test_hotkeys_and_privacy():
    assert parse_hotkey("Ctrl+Alt+Space") == (0x4003, 0x20)
    with pytest.raises(ValueError):
        parse_hotkey("Ctrl+Invalid")
    assert PrivacyFilter("bitwarden,incognito").excluded("chrome.exe", "Incognito tab")


def test_conversation_retention(tmp_path):
    from companion.storage import ConversationStore
    store = ConversationStore(tmp_path / "history.db")
    store.save("Question", "Answer", 7)
    assert store.read()[0][1:] == ("Question", "Answer")
    store.clear()
    assert store.read() == []
