"""Local intent and reasoning routing: never call a model to select another model."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Intent:
    screen: bool = False
    temporal: bool = False
    audio: bool = False
    followup: bool = False
    current: bool = False
    complex: bool = False


def classify(text):
    screen = bool(re.search(r"\b(screen|button|symbol|notification|dialog|disappear|visible|window|this code|this error|that drawing|this equation|my drawing|ekran|symbol|przycisk)\b", text, re.I))
    screen = screen or bool(re.search(r"\bdisappear\w*\b|\b(?:this|that|my)\s+(?:(?:Unity|Unreal|Python|Minecraft)\s+)?(?:code|algorithm|drawing|equation|error|symbol|button|block|game|program)\b", text, re.I))
    temporal = bool(re.search(r"\b(happened|changed|disappear|notification|before|ago|yesterday|wcześniej|znikn|stało)\b", text, re.I))
    audio = bool(re.search(r"\b(lecturer|speaker|he mean|she mean|said|audio|lecture|video|narrator|powiedział|wykład)\b", text, re.I))
    followup = bool(re.search(r"^(and |why is that important|how would that|explain that|give me an example|go deeper|continue|summari|a jak|wyjaśnij to)", text, re.I))
    current = bool(re.search(r"\b(latest|currently|news|update|current|today|najnowsz|aktualn|dzisiaj)\b", text, re.I))
    complex_q = bool(re.search(r"\b(prove|derive|advanced|deeply|algorithm|analyse|analyze|research|in depth|dokładnie|udowodnij)\b", text, re.I))
    if re.search(r"\b(what happened to that|why did that|what does that symbol|what does this)\b", text, re.I):
        screen = True
    return Intent(screen, temporal and (screen or audio), audio, followup, current, complex_q)


@dataclass(frozen=True)
class Route:
    provider: str
    intent: Intent
    confirm: bool = False
    note: str = ""
    web: bool = False


class ReasoningRouter:
    def select(self, question, settings):
        kind = classify(question)
        local_override = bool(re.search(r"\b(answer locally|local only|don't use cloud|odpowiedz lokalnie)\b", question, re.I))
        cloud_override = bool(re.search(r"\b(use cloud|cloud ai|użyj chmury)\b", question, re.I))
        no_web = bool(re.search(r"\b(don.t use the internet|no internet|offline|bez internetu)\b", question, re.I))
        web = settings.web_access and kind.current and not no_web
        wants_cloud = cloud_override or settings.mode in {"cloud", "confirm"} or (settings.mode == "hybrid" and (kind.complex or settings.preset == "gaming"))
        if local_override or settings.mode == "local" or not settings.cloud_access or not wants_cloud:
            note = "A stronger cloud model may help; cloud escalation is disabled." if kind.complex else ""
            return Route(settings.local_provider, kind, note=note, web=web)
        if settings.escalation == "never" and not cloud_override and settings.mode != "confirm":
            return Route(settings.local_provider, kind, note="Cloud escalation requires an explicit request.", web=web)
        return Route(settings.cloud_provider, kind,
                     confirm=settings.escalation == "ask" or settings.mode == "confirm", web=web)
