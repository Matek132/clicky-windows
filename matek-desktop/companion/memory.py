"""Adapt the shared Screenpipe client to Matek's existing capture/context engine."""
import base64
from dataclasses import replace
import threading
import time
from datetime import datetime
from .context import Frame, Transcript
from .security import Credentials
from memory_backend import LocalMemory, MemorySettings, intent, time_window


def context_intent(question):
    import re
    screen, audio = intent(question)
    screen = screen or bool(re.search(r"\b(changed|different|before|what does this|what does that|why did that|why is this)\b", question, re.I))
    return screen, audio


class CompanionMemory:
    def __init__(self, settings):
        self.settings = settings
        self.client = LocalMemory(MemorySettings(enabled=settings.memory_backend == "screenpipe",
            url=settings.screenpipe_url, retention_days=settings.screenpipe_retention_days,
            screen=settings.continuous_screen or settings.manual_screenshots,
            audio=settings.system_audio, exclusions=settings.exclusions,
            max_images=min(settings.max_request_images, 3)),
            token_factory=lambda: Credentials.get("screenpipe:" + settings.screenpipe_url))
        self.stop = threading.Event()
        self.screen_owned = False
        self.audio_owned = False

    def start(self):
        if not self.client.settings.enabled:
            return
        stop = self.stop = threading.Event()
        def watch():
            while not stop.is_set():
                try:
                    health = self.client.request("/health")
                    if stop.is_set():
                        return
                    self.update_health(health)
                except Exception:
                    self.screen_owned = self.audio_owned = False
                stop.wait(5)
        threading.Thread(target=watch, daemon=True, name="memory-health").start()

    def update_health(self, health):
        def fresh(value):
            try:
                age = time.time() - datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
                return -5 <= age <= 30
            except (ValueError, TypeError, AttributeError):
                return False
        self.screen_owned = health.get("frame_status") == "ok" and fresh(health.get("last_frame_timestamp"))
        self.audio_owned = health.get("audio_status") == "ok" and fresh(health.get("last_audio_timestamp"))

    def owns(self, source):
        return self.client.settings.enabled and (self.screen_owned if source == "screen" else self.audio_owned if source == "system" else False)

    def select(self, package):
        screen, audio = context_intent(package.question)
        package = replace(package, frames=package.frames if screen else (), transcripts=package.transcripts if audio else ())
        if self.client.settings.enabled and (screen or audio):
            result = self.client.retrieve(package.question)
            if result.backend == "screenpipe":
                frames = tuple(Frame(row.at, base64.b64decode(row.image), row.app, row.title, row.text)
                               for row in result.records if row.kind == "screen" and row.image)
                transcripts = tuple(Transcript(row.at, row.text, "system") for row in result.records if row.kind == "audio")
                return replace(package, frames=frames, transcripts=transcripts, notes=result.prompt())
        start, end = time_window(package.question, package.at, self.settings.screenpipe_retention_days)
        frames = tuple(row for row in package.frames if start <= row.at <= end)
        transcripts = tuple(row for row in package.transcripts if start <= row.at <= end)
        return replace(package, frames=frames, transcripts=transcripts,
                       notes=package.notes + " RAM memory covers only the last two minutes; older events are unavailable.")

    def close(self):
        self.stop.set()
        self.screen_owned = self.audio_owned = False
        self.client.close()
