from dataclasses import dataclass, field
import hashlib
import time
import threading
import uuid
from .providers import instructions, Cancelled


@dataclass(frozen=True)
class Prepared:
    package: object
    settings: object
    estimate: float
    rate: dict | None
    requires_confirmation: bool
    identity: str = field(default_factory=lambda: uuid.uuid4().hex)


class RequestController:
    """The only application path allowed to invoke a reasoning provider."""
    def __init__(self, ledger, clock=time.time):
        self.ledger = ledger
        self.clock = clock
        self.lock = threading.Lock()
        self.recent = {}
        self.used_preparations = set()

    def prepare(self, package, settings):
        if not package.question.strip():
            raise ValueError("Enter a question first.")
        if package.source not in {"typed", "microphone", "system", "manual"}:
            raise PermissionError("Unknown question source.")
        if package.source == "microphone" and not settings.microphone:
            raise PermissionError("Microphone permission has been revoked.")
        if package.source == "system" and not (settings.system_audio and settings.system_questions):
            raise PermissionError("System-audio question activation is disabled.")
        if settings.mode == "local":
            return Prepared(package, settings, 0, None, False)
        if not settings.cloud_access:
            raise PermissionError("Cloud transmission is disabled. Enable it in Privacy settings or select Local mode.")
        estimate, rate = self.ledger.estimate(package, settings, instructions(settings))
        self.ledger.check(estimate, settings)
        return Prepared(package, settings, estimate, rate,
                        settings.mode == "confirm" or estimate >= settings.confirm_above_usd)

    def execute(self, prepared, provider, cancel, on_chunk, approved=False):
        if prepared.requires_confirmation and not approved:
            raise PermissionError("This request requires confirmation before transmission.")
        if self.clock() - prepared.package.at > 120:
            raise PermissionError("This question has expired. Ask again for fresh context.")
        if cancel.is_set():
            raise Cancelled()
        with self.lock:
            debounce = 2 if prepared.settings.mode == "local" else 15
            self.recent = {key: at for key, at in self.recent.items() if self.clock() - at < debounce}
            key = hashlib.sha256(prepared.package.question.strip().casefold().encode()).hexdigest()
            if key in self.recent or prepared.identity in self.used_preparations:
                raise PermissionError(f"Duplicate question blocked. Wait {debounce} seconds before repeating it.")
            self.recent[key] = self.clock()
            self.used_preparations.add(prepared.identity)
            if len(self.used_preparations) > 10000:
                self.used_preparations.clear()
                self.used_preparations.add(prepared.identity)
        identity = None
        if prepared.settings.mode != "local":
            identity = self.ledger.reserve(prepared.estimate, prepared.settings)
        try:
            usage = provider.stream(prepared.package, prepared.settings, cancel, on_chunk)
        except Exception:
            if identity:
                self.ledger.settle(identity, "cancelled/unknown" if cancel.is_set() else "failed/unknown")
            raise
        if identity:
            self.ledger.settle(identity, "completed" if usage else "completed/estimated", usage, prepared.rate)
