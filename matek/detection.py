import re
import time


class QuestionDetector:
    def __init__(self, settings, clock=time.time):
        self.settings = settings
        self.clock = clock
        self.last = -1e12

    def wake_match(self, text):
        phrases = [re.escape(x.strip()) for x in self.settings.wake_words.split(",") if x.strip()]
        # Common offline recognition spellings of the companion's name.
        if "matek" in self.settings.wake_words.casefold().split(","):
            phrases += ["mateck", "matech", "maytek", "matic", "matec"]
        return re.match(r"^(?:hey\s+)?(?:" + "|".join(phrases) + r")\b[\s,.:!?-]*(.+)$", text.strip(), re.I) if phrases else None

    def addressed(self, text):
        return bool(re.match(r"^(?:hey\s+)?(?:matek|mateck|matech|maytek|matic|matec)\b", text.strip(), re.I))

    @staticmethod
    def incomplete(text):
        words = re.findall(r"\w+", text.casefold())
        if not words:
            return False
        phrase = " ".join(words)
        if phrase in {"how do i", "how can i", "how should i", "how would i", "what should i",
                      "what is", "why is", "where is", "who is", "how do", "how does", "what does",
                      "why does", "can you", "could you", "would you"}:
            return True
        if words[-1] in {"the", "a", "an", "and", "or", "but", "because", "if", "whether"}:
            return True
        if words[0] in {"how", "can", "could"} and words[-1] in {"to", "with", "about", "for", "craft", "build", "make"}:
            return True
        return False

    def detect(self, text, source, confidence=1.0, manual=False):
        text = text.strip()
        if not text or confidence < self.settings.confidence:
            return None
        if source == "system" and not self.settings.system_questions:
            return None
        if manual:
            return text
        if self.settings.activation == "push":
            return None
        match = self.wake_match(text)
        if self.settings.activation == "wake":
            if not match:
                return None
            text = match.group(1)
        else:
            if match:
                text = match.group(1)
            text = re.sub(r"^(?:(?:um|uh|so|okay|ok|well)[,\s]+|(?:i was wondering|i wonder|do you know)\s+)+", "", text, flags=re.I)
            question = bool(re.match(r"^(what|why|who|where|when|how|which|can|could|would|should|is|are|do|does|did|explain|tell me|and|give me|go deeper|continue|summarise|summarize|short answer|next|stop|repeat|say it again|co|czym|jak|dlaczego|kiedy|gdzie|wyjaśnij|powtórz|przestań)\b", text, re.I))
            if not question and not match:
                return None
        if self.clock() - self.last < self.settings.debounce_seconds:
            return None
        self.last = self.clock()
        return text
