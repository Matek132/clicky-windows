from dataclasses import dataclass, asdict, fields
import json
import os
import math
from pathlib import Path


def data_dir():
    path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MatekScreenCompanion"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Settings:
    mode: str = "local"
    local_provider: str = "ollama"
    lmstudio_url: str = "http://127.0.0.1:1234/v1"
    cloud_provider: str = "openai"
    escalation: str = "ask"
    web_access: bool = False
    speech_policy: str = "wake"
    response_language: str = ""
    interrupt_questions: bool = False
    cursor_mode: bool = False
    proactive: bool = False
    microphone: bool = False
    system_audio: bool = False
    continuous_screen: bool = False
    manual_screenshots: bool = False
    cloud_access: bool = False
    persistent_history: bool = False
    mic_device: int = -1
    system_device: int = -1
    activation: str = "push"
    system_questions: bool = False
    wake_words: str = "matek,assistant,hey companion"
    confidence: float = 0.65
    debounce_seconds: float = 8.0
    vad_aggressiveness: int = 2
    mic_gain: float = 1.0
    mic_noise_floor: int = 110
    end_pause_seconds: float = 4.0
    max_question_seconds: int = 90
    speech_output: bool = True
    speech_voice: str = ""
    speech_rate: float = 0.0
    speech_volume: float = 0.85
    echo_guard: bool = True
    allow_voice_commands_during_speech: bool = True
    answer_display_seconds: int = 18
    whisper_model: str = "models/whisper-base"
    whisper_device: str = "cpu"
    whisper_threads: int = 2
    language: str = ""
    monitor: int = 1
    capture_seconds: float = 5.0
    retention_seconds: int = 120
    memory_backend: str = "ram"
    screenpipe_url: str = "http://127.0.0.1:3030"
    screenpipe_retention_days: int = 7
    screen_memory_mb: int = 64
    max_frames: int = 24
    image_max_side: int = 1280
    max_request_images: int = 3
    ocr: bool = True
    tesseract_path: str = ""
    exclusions: str = "1password,bitwarden,keepass,lastpass,password manager,inprivate,incognito,banking"
    model: str = "gpt-4.1-mini"
    api_base: str = "https://api.openai.com/v1"
    local_url: str = "http://127.0.0.1:11434"
    local_model: str = "qwen2.5vl:3b"
    local_text_model: str = ""
    local_vision: bool = False
    knowledge_enabled: bool = True
    knowledge_folder: str = ""
    verbosity: str = "quick"
    preset: str = "balanced"
    max_output_tokens: int = 700
    daily_usd: float = 1.0
    monthly_usd: float = 10.0
    per_question_usd: float = 0.08
    confirm_above_usd: float = 0.04
    conversation_turns: int = 12
    conversation_retention_days: int = 7
    opacity: float = 0.97
    always_on_top: bool = True
    click_through: bool = False
    launch_minimized: bool = False
    start_with_windows: bool = False
    overlay_x: int = -1
    overlay_y: int = -1
    hotkey_ask: str = "Ctrl+Alt+Space"
    hotkey_toggle: str = "Ctrl+Alt+O"
    hotkey_pause: str = "Ctrl+Alt+P"
    hotkey_clear: str = "Ctrl+Alt+Backspace"
    hotkey_capture: str = "Ctrl+Alt+S"

    def validate(self):
        defaults = Settings()
        for entry in fields(self):
            value = getattr(self, entry.name)
            expected = type(getattr(defaults, entry.name))
            valid = isinstance(value, (int, float)) and not isinstance(value, bool) if expected is float else type(value) is expected
            if not valid or (isinstance(value, (int, float)) and not math.isfinite(value)):
                raise ValueError(f"Invalid value for {entry.name}")
        choices = {"mode": {"hybrid", "cloud", "confirm", "local"}, "local_provider": {"ollama", "lmstudio"}, "cloud_provider": {"openai", "claude", "gemini", "copilot", "lmstudio"},
                   "escalation": {"ask", "budget", "never"}, "speech_policy": {"wake", "full", "summary", "text", "auto", "speech"},
                   "memory_backend": {"ram", "screenpipe"}, "activation": {"push", "wake", "automatic"},
                   "verbosity": {"quick", "balanced", "detailed", "research"},
                   "preset": {"balanced", "gaming", "programming", "study", "research", "media", "offline"},
                   "whisper_device": {"cpu", "cuda"}}
        for name, options in choices.items():
            if getattr(self, name) not in options:
                raise ValueError(f"Invalid {name}")
        ranges = {"capture_seconds": (1, 60), "retention_seconds": (10, 120), "screen_memory_mb": (4, 256),
                  "max_frames": (2, 60), "image_max_side": (320, 2048), "max_request_images": (1, 4),
                  "max_output_tokens": (100, 8000), "confidence": (0, 1), "opacity": (0.3, 1),
                  "vad_aggressiveness": (0, 3), "mic_gain": (0.1, 5), "whisper_threads": (1, 8),
                  "conversation_turns": (0, 50), "conversation_retention_days": (1, 365),
                  "monitor": (1, 16), "debounce_seconds": (1, 120)}
        ranges.update({"end_pause_seconds": (1, 10), "max_question_seconds": (30, 180),
                       "screenpipe_retention_days": (1, 365),
                       "speech_rate": (-0.5, 0.5), "speech_volume": (0, 1), "answer_display_seconds": (5, 120),
                       "mic_noise_floor": (0, 3000)})
        for name, (low, high) in ranges.items():
            if not low <= getattr(self, name) <= high:
                raise ValueError(f"{name} must be between {low} and {high}")
        for name in ("daily_usd", "monthly_usd", "per_question_usd", "confirm_above_usd"):
            if not 0 <= getattr(self, name) <= 1000:
                raise ValueError(f"Invalid budget: {name}")
        from urllib.parse import urlparse
        remote = urlparse(self.api_base)
        if remote.scheme != "https" or not remote.hostname or remote.username or remote.password:
            raise ValueError("Cloud endpoint must use HTTPS without embedded credentials")
        local = urlparse(self.local_url)
        if local.scheme != "http" or local.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Local model endpoint must be loopback HTTP")
        studio = urlparse(self.lmstudio_url)
        if studio.scheme != "http" or studio.hostname not in {"127.0.0.1", "localhost", "::1"} or studio.username or studio.password:
            raise ValueError("LM Studio must use loopback HTTP")
        if ":cloud" in self.local_model.lower():
            raise ValueError("Cloud-hosted Ollama models cannot be used as a local backend")
        from memory_backend import MemorySettings
        MemorySettings(url=self.screenpipe_url, retention_days=self.screenpipe_retention_days).validate()

    @classmethod
    def load(cls, path=None):
        path = path or data_dir() / "settings.json"
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        result = cls(**{k: v for k, v in raw.items() if k in known})
        result.validate()
        return result

    def save(self, path=None):
        self.validate()
        path = path or data_dir() / "settings.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        temp.replace(path)
