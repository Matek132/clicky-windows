"""Apply per-request authorization and accounting around existing Clicky providers."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import hashlib
import time
from ai.base_provider import BaseLLMProvider


class CloudRequestController:
    def __init__(self, ledger):
        self.ledger = ledger
        self.recent = {}

    def admit_question(self, question):
        now = time.time()
        self.recent = {key: stamp for key, stamp in self.recent.items() if now - stamp < 2}
        key = hashlib.sha256(question.casefold().strip().encode()).hexdigest()
        if key in self.recent:
            raise PermissionError("Duplicate question · please wait two seconds")
        self.recent[key] = now


class GuardedProvider(BaseLLMProvider):
    def __init__(self, manager, provider, name):
        self.manager, self.provider, self.name = manager, provider, name

    async def stream_response(self, **kwargs):
        manager = self.manager
        scope = manager.scope
        if scope is None or time.time() - scope.started > 120 or manager._cancel_flag:
            raise PermissionError("No active authorized question")
        remote = self.name not in {"ollama", "lmstudio"}
        main_answer = kwargs.get("user_text") == scope.question
        if main_answer:
            kwargs["history"] = kwargs.get("history", [])[-12:] if manager.route.intent.followup else []
        if remote and (not manager.settings.cloud_access or manager.settings.mode == "local"):
            raise PermissionError("Cloud access disabled")
        token_bound = max(4096, manager.settings.max_output_tokens)
        cfg = replace(manager.settings, model=kwargs.get("model") or manager.settings.model,
                      api_base=self.name, max_output_tokens=token_bound)
        if self.name == "openai" and manager.settings.api_base.rstrip("/") != "https://api.openai.com/v1":
            cfg = replace(cfg, api_base=manager.settings.api_base)
        reservation = None
        rate = None
        if remote:
            from .security import PrivacyFilter
            if PrivacyFilter.sensitive_text(kwargs.get("user_text", "")) or any(PrivacyFilter.sensitive_text(m.content) for m in kwargs.get("history", [])):
                raise PermissionError("Sensitive credential text detected · use Local Only or remove it before a cloud request")
            from json import dumps
            package = SimpleNamespace(text=lambda: dumps({key: value for key, value in kwargs.items() if key != "screenshots_b64"}, default=str),
                                      conversation=(), frames=kwargs.get("screenshots_b64", []))
            estimate, rate = manager.ledger.estimate(package, cfg, "")
            manager.ledger.check(estimate, cfg)
            if scope.spent_estimate + estimate > cfg.per_question_usd:
                raise PermissionError("Total request/pointing cost exceeds per-question limit")
            if manager.route.confirm or estimate >= cfg.confirm_above_usd:
                if not await manager.confirm_cloud(estimate, kwargs):
                    raise PermissionError("Cloud request declined · nothing transmitted")
            if manager._cancel_flag or not manager.settings.cloud_access:
                raise PermissionError("Request cancelled before transmission")
            reservation = manager.ledger.reserve(estimate, cfg)
            scope.spent_estimate += estimate
        kwargs["model"] = cfg.model if remote else manager.local_model_override if self.name == "ollama" else None
        if not remote and not manager.settings.local_vision:
            kwargs["screenshots_b64"] = []
        answer = []
        try:
            self.provider.last_usage = None
            async for chunk in self.provider.stream_response(**kwargs):
                if manager._cancel_flag:
                    raise asyncio.CancelledError()
                if main_answer:
                    answer.append(chunk)
                    manager.speech_feed.emit((scope.speech_token, chunk))
                yield chunk
            if reservation:
                usage = getattr(self.provider, "last_usage", None)
                manager.ledger.settle(reservation, "completed" if usage else "completed/estimated", usage, rate)
            if main_answer:
                scope.answer = "".join(answer)
        except BaseException:
            if reservation:
                manager.ledger.settle(reservation, "failed/cancelled/unknown")
            raise

    async def health_check(self):
        return await self.provider.health_check()

    async def close(self):
        if hasattr(self.provider, "close"):
            await self.provider.close()
