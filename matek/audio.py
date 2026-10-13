from collections import deque
from contextlib import contextmanager
from pathlib import Path
import queue
import threading
import time
import numpy as np
from .context import Transcript


_audio_lifecycle_lock = threading.RLock()


@contextmanager
def audio_manager():
    """PortAudio initialization/termination is process-global and not thread safe."""
    import pyaudiowpatch as pa
    with _audio_lifecycle_lock:
        manager = pa.PyAudio()
    try:
        yield manager
    finally:
        with _audio_lifecycle_lock:
            manager.terminate()


class SpeechSegmenter:
    """Bounded 15s chunks; only sustained silence or utterance limit ends a question."""
    def __init__(self, aggressiveness=2, end_pause=4.0, max_question_seconds=90, noise_floor=0):
        import webrtcvad
        self.vad = webrtcvad.Vad(aggressiveness)
        self.pre = deque(maxlen=10)
        self.frames = []
        self.voiced = 0
        self.utterance_voiced = 0
        self.silence = 0
        self.end_frames = round(end_pause / .03)
        self.max_question_frames = round(max_question_seconds / .03)
        self.total_frames = 0
        self.active = False
        self.is_final = True
        self.session = time.monotonic_ns()
        self.noise_floor = noise_floor
        self.truncated = False
        self.discarding = False

    def feed(self, pcm):
        voice = self.vad.is_speech(pcm, 16000)
        if self.noise_floor:
            samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
            voice = voice and float(np.sqrt(np.mean(samples * samples))) >= self.noise_floor
        if self.discarding:
            self.silence = 0 if voice else self.silence + 1
            if self.silence >= self.end_frames:
                self.discarding = False
                self.active = False
                self.silence = 0
            return None
        self.pre.append(pcm)
        if not self.active:
            if voice:
                self.voiced += 1
                if self.voiced >= 3:
                    self.frames = list(self.pre)
                    self.silence = 0
                    self.active = True
                    self.total_frames = len(self.frames)
                    self.utterance_voiced = self.voiced
                    self.session += 1
                    self.truncated = False
            else:
                self.voiced = 0
            return None
        self.frames.append(pcm)
        self.total_frames += 1
        self.utterance_voiced += int(voice)
        self.silence = 0 if voice else self.silence + 1
        if self.silence >= self.end_frames or self.total_frames >= self.max_question_frames or len(self.frames) >= 500:
            self.is_final = self.silence >= self.end_frames or self.total_frames >= self.max_question_frames
            # Waiting for a thinking pause does not require transcribing all of
            # its trailing silence. Ignore very short acoustic clicks entirely.
            retained = self.frames[:max(1, len(self.frames) - max(0, self.silence - 10))] if self.is_final else self.frames
            result = b"".join(retained) if self.utterance_voiced >= 5 else None
            self.truncated = self.total_frames >= self.max_question_frames and self.silence < self.end_frames
            # Overlap protects words crossing a chunk boundary. This is not a final-question event.
            self.frames = [] if self.is_final else self.frames[-10:]
            self.pre.clear()
            self.voiced = 0
            if self.is_final:
                self.silence = 0
                self.active = self.truncated
                self.discarding = self.truncated
            return result
        return None

    def flush(self):
        if not self.frames:
            return None
        result = b"".join(self.frames)
        self.frames = []
        self.pre.clear()
        self.active = False
        self.voiced = self.silence = 0
        self.is_final = True
        self.truncated = False
        return result


def join_transcript(previous, incoming):
    left, right = previous.split(), incoming.split()
    normalize = lambda word: word.strip(".,!?;:").casefold()
    for count in range(min(8, len(left), len(right)), 0, -1):
        if [normalize(w) for w in left[-count:]] == [normalize(w) for w in right[:count]]:
            right = right[count:]
            break
    return " ".join(left + right)[:12000]


def mono_input(raw, channels, source):
    samples = np.frombuffer(raw, dtype=np.int16).reshape(-1, channels).astype(np.float32)
    if source == "microphone":
        # Stereo interfaces often have a microphone on only one input. Averaging
        # attenuates it, or cancels opposite-polarity channels entirely.
        strongest = int(np.argmax(np.mean(samples * samples, axis=0)))
        return samples[:, strongest]
    return samples.mean(axis=1)


class Transcriber:
    def __init__(self, settings):
        self.settings = settings
        self.model = None

    def transcribe(self, pcm, source, at=None):
        cfg = self.settings
        if self.model is None:
            from faster_whisper import WhisperModel
            model_path = Path(cfg.whisper_model).resolve()
            if not model_path.is_dir():
                raise RuntimeError("Offline speech model missing. Run scripts\\download_model.bat before enabling audio.")
            try:
                self.model = WhisperModel(str(model_path), device=cfg.whisper_device, compute_type="int8",
                                          cpu_threads=cfg.whisper_threads, num_workers=1, local_files_only=True)
            except Exception as exc:
                if cfg.whisper_device != "cuda":
                    raise RuntimeError("Speech model failed to load. Check the local model folder.") from exc
                self.model = WhisperModel(str(model_path), device="cpu", compute_type="int8",
                                          cpu_threads=cfg.whisper_threads, num_workers=1, local_files_only=True)
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        segments, _ = self.model.transcribe(samples, language=cfg.language or None, beam_size=1,
                                            condition_on_previous_text=False, initial_prompt="Matek")
        segments = [s for s in segments if s.no_speech_prob < 0.65]
        text = " ".join(s.text.strip() for s in segments)
        confidence = float(np.mean([min(1, np.exp(s.avg_logprob)) for s in segments])) if segments else 0
        return Transcript(at or time.time(), text, source, confidence)


def devices():
    with audio_manager() as audio:
        return [{"index": d["index"], "name": d["name"], "loopback": bool(d.get("isLoopbackDevice"))}
                for d in audio.get_device_info_generator() if d["maxInputChannels"] > 0]


class AudioService:
    def __init__(self, settings, on_transcript, on_status, on_activity=None, suppression=None, source_owned=None):
        self.settings = settings
        self.on_transcript = on_transcript
        self.on_status = on_status
        self.stop = threading.Event()
        self.segments = queue.Queue(maxsize=4)
        self.threads = []
        self.transcriber = Transcriber(settings)
        self.transcriptions = 0
        self.transcription_seconds = 0.0
        self.on_activity = on_activity or (lambda source, active: None)
        self.suppression = suppression or threading.Event()
        self.dropped_sessions = deque(maxlen=32)
        self.finish_microphone = threading.Event()
        self.source_owned = source_owned or (lambda source: False)

    def start(self):
        if not (self.settings.microphone or self.settings.system_audio):
            return
        thread = threading.Thread(target=self._transcribe, daemon=True, name="local-stt")
        thread.start()
        self.threads.append(thread)
        for source, enabled in (("microphone", self.settings.microphone), ("system", self.settings.system_audio)):
            if enabled:
                thread = threading.Thread(target=self._capture, args=(source,), daemon=True, name=source)
                thread.start()
                self.threads.append(thread)

    def close(self):
        self.stop.set()
        # Do not block Qt while a local model finishes a segment.
        while True:
            try:
                self.segments.get_nowait()
            except queue.Empty:
                break

    def _capture(self, source):
        import pyaudiowpatch as pa
        while not self.stop.is_set():
            if self.source_owned(source):
                self.stop.wait(.5)
                continue
            try:
                with audio_manager() as audio:
                    index = self.settings.mic_device if source == "microphone" else self.settings.system_device
                    if index < 0:
                        device = audio.get_default_wasapi_loopback() if source == "system" else audio.get_default_input_device_info()
                    else:
                        device = audio.get_device_info_by_index(index)
                    if source == "system" and not device.get("isLoopbackDevice"):
                        raise RuntimeError("Select a loopback device for system audio")
                    if source == "microphone" and device.get("isLoopbackDevice"):
                        raise RuntimeError("Loopback cannot be selected as a microphone")
                    rate = int(device["defaultSampleRate"])
                    channels = int(device["maxInputChannels"])
                    count = int(rate * 0.03)
                    end_pause = self.settings.end_pause_seconds if source == "microphone" else .7
                    vad = SpeechSegmenter(self.settings.vad_aggressiveness, end_pause,
                                          self.settings.max_question_seconds if source == "microphone" else 86400,
                                          self.settings.mic_noise_floor if source == "microphone" else 0)
                    with audio.open(format=pa.paInt16, channels=channels, rate=rate, input=True,
                                    input_device_index=int(device["index"]), frames_per_buffer=count) as stream:
                        self.on_status(f"Listening locally · {source}")
                        while not self.stop.is_set():
                            if self.source_owned(source):
                                self.on_activity(source, False)
                                break
                            raw = stream.read(count, exception_on_overflow=False)
                            if self.stop.is_set():
                                break
                            if self.suppression.is_set() and (source == "system" or not getattr(self.settings, "allow_voice_commands_during_speech", False)):
                                if vad.active:
                                    self.on_activity(source, False)
                                vad = SpeechSegmenter(self.settings.vad_aggressiveness, end_pause,
                                                      self.settings.max_question_seconds if source == "microphone" else 86400,
                                                      self.settings.mic_noise_floor if source == "microphone" else 0)
                                continue
                            samples = mono_input(raw, channels, source)
                            vad.end_frames = round((.65 if self.suppression.is_set() and source == "microphone" else end_pause) / .03)
                            # Bounded interpolation to exactly 480 mono samples (30ms at 16kHz).
                            mono = np.interp(np.arange(480) * len(samples) / 480, np.arange(len(samples)), samples)
                            gain = self.settings.mic_gain if source == "microphone" else 1
                            pcm = np.clip(mono * gain, -32768, 32767).astype(np.int16).tobytes()
                            was_active = vad.active
                            if source == "microphone" and self.finish_microphone.is_set():
                                self.finish_microphone.clear()
                                segment = vad.flush()
                            else:
                                segment = vad.feed(pcm)
                            if was_active != vad.active:
                                self.on_activity(source, vad.active)
                            if segment:
                                try:
                                    final = vad.is_final if source == "microphone" else True
                                    session = vad.session if source == "microphone" else time.monotonic_ns()
                                    self.segments.put_nowait((segment, source, time.time(), final, session, vad.truncated))
                                except queue.Full:
                                    # Never submit a known-incomplete question after dropping part of it.
                                    self.on_status("Audio backlog full · question skipped; please repeat")
                                    self.dropped_sessions.append((source, vad.session))
            except Exception:
                self.on_status(f"{source.capitalize()} unavailable · retrying locally in 5 seconds")
                self.stop.wait(5)

    def _transcribe(self):
        pending = {}
        while not self.stop.is_set():
            try:
                pcm, source, at, final, session, truncated = self.segments.get(timeout=0.25)
            except queue.Empty:
                expiry = time.time() - self.settings.max_question_seconds - self.settings.end_pause_seconds
                pending = {key: value for key, value in pending.items() if value[0] >= expiry}
                continue
            try:
                key = (source, session)
                for stale in list(pending):
                    if stale[0] == source and stale != key:
                        pending.pop(stale, None)
                if key in self.dropped_sessions:
                    pending.pop(key, None)
                    continue
                started = time.monotonic()
                snippet = self.transcriber.transcribe(pcm, source, at)
                self.transcriptions += 1
                self.transcription_seconds += time.monotonic() - started
                if self.suppression.is_set() and (source == "system" or not getattr(self.settings, "allow_voice_commands_during_speech", False)):
                    pending.clear()
                    continue
                _, text, scores = pending.get(key, (at, "", []))
                text = join_transcript(text, snippet.text)
                if snippet.text:
                    scores.append(snippet.confidence)
                pending[key] = (at, text, scores)
                if not self.stop.is_set() and text:
                    self.on_transcript(Transcript(at, text, source, float(np.mean(scores)) if scores else 0,
                                                  final, session, truncated))
                if final:
                    pending.pop(key, None)
            except Exception as exc:
                self.dropped_sessions.append((source, session))
                pending.pop((source, session), None)
                # Own errors are actionable and do not include audio or credentials.
                self.on_status(str(exc) if isinstance(exc, RuntimeError) else "Local transcription failed. Check the model and device.")
                self.stop.wait(5)
            finally:
                pcm = None  # Do not retain the last recording while waiting for the next utterance.
