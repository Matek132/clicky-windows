"""Offline Windows speech with streamed sentence playback and actual word progress."""
from collections import deque
import re
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtTextToSpeech import QTextToSpeech


def plain_speech(text):
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*]\s+)", "", text)
    return text.replace("```", "").replace("`", "").replace("**", "").strip()


def utf16_prefix(text, length):
    return text.encode("utf-16-le")[:length * 2].decode("utf-16-le", errors="ignore")


class SpokenAnswer(QObject):
    text_changed = Signal(str)
    speaking_changed = Signal(bool)
    completed = Signal()
    error = Signal(str)

    def __init__(self, settings, parent=None, engine=None):
        super().__init__(parent)
        self.settings = settings
        engines = QTextToSpeech.availableEngines()
        self.tts = engine or (QTextToSpeech("sapi", self) if "sapi" in engines else None)
        if self.tts:
            self.tts.stateChanged.connect(self._state)
            self.tts.sayingWord.connect(self._word)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.setInterval(190)
        self.reset()
        self.configure(settings)

    def configure(self, settings):
        self.settings = settings
        if self.tts:
            self.tts.setRate(settings.speech_rate)
            self.tts.setVolume(settings.speech_volume)
            for voice in self.tts.availableVoices():
                if voice.name() == settings.speech_voice:
                    self.tts.setVoice(voice)

    @property
    def speaking(self):
        return self.active and self.use_voice

    def reset(self):
        self.active = False
        self.use_voice = False
        self.finished_input = False
        self.pending = ""
        self.queue = deque()
        self.current = ""
        self.displayed = ""
        self.word_index = 0
        self.current_words = []
        self.timer.stop()

    def cancel(self):
        self.active = False
        self.queue.clear()
        self.pending = ""
        if self.tts:
            self.tts.stop(QTextToSpeech.BoundaryHint.Immediate)
        self.reset()
        self.speaking_changed.emit(False)

    def feed(self, chunk):
        self.pending += chunk
        if not self.settings.speech_output:
            # Text appears as soon as streamed words arrive; it never waits for
            # punctuation or the speech engine to start.
            while True:
                boundary = re.search(r"\s+", self.pending)
                if not boundary:
                    break
                text, self.pending = self.pending[:boundary.start()], self.pending[boundary.end():]
                self._enqueue(text)
            return
        while True:
            boundary = re.search(r"[.!?](?=\s|$)|\n", self.pending)
            if not boundary:
                break
            text, self.pending = self.pending[:boundary.end()], self.pending[boundary.end():]
            self._enqueue(text)

    def finish(self):
        self.finished_input = True
        self._enqueue(self.pending)
        self.pending = ""
        if not self.active and not self.queue:
            self.completed.emit()

    def _enqueue(self, text):
        text = plain_speech(text)
        if text:
            self.queue.append(text)
            self._next()

    def _next(self):
        if self.active or not self.queue:
            return
        self.current = self.queue.popleft()
        self.active = True
        self.word_index = 0
        self.current_words = self.current.split()
        if self.settings.speech_output and self.tts and self.tts.state() != QTextToSpeech.State.Error:
            self.use_voice = True
            self.speaking_changed.emit(True)
            self.tts.say(self.current)
        else:
            self.use_voice = False
            if self.settings.speech_output and not self.tts:
                self.error.emit("Offline Windows voice unavailable · text captions remain enabled")
            self.timer.start()

    def _word(self, word, identity, start, length):
        if self.active:
            prefix = utf16_prefix(self.current, start + length)
            self.text_changed.emit((self.displayed + " " + prefix).strip())

    def _tick(self):
        if not self.active:
            self.timer.stop()
            return
        self.word_index += 1
        self.text_changed.emit((self.displayed + " " + " ".join(self.current_words[:self.word_index])).strip())
        if self.word_index >= len(self.current_words):
            self._end()

    def _state(self, state):
        if state == QTextToSpeech.State.Ready and self.active:
            self._end()
        elif state == QTextToSpeech.State.Error and self.active:
            self.use_voice = False
            self.speaking_changed.emit(False)
            self.error.emit("Voice playback failed · showing text instead")
            self.timer.start()

    def _end(self):
        self.timer.stop()
        self.displayed = (self.displayed + " " + self.current).strip()
        self.text_changed.emit(self.displayed)
        self.active = False
        if self.queue:
            self._next()
        else:
            self.speaking_changed.emit(False)
            if self.finished_input:
                self.completed.emit()
