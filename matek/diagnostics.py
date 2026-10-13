"""Local native acceptance/measurement using generated assets and isolated data."""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import threading
import time
import wave


def run(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-check", action="store_true")
    parser.add_argument("--benchmark", choices=["normal", "synthetic-gpu"])
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--monitoring", choices=["all", "microphone", "system", "screen"], default="all")
    parser.add_argument("--model", type=Path, default=Path("models/whisper-base"))
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    from PyQt6.QtWidgets import QApplication, QLabel
    from PyQt6.QtCore import QTimer, Qt
    from .config import Settings, data_dir
    from .manager import MatekManager
    from .panel import MatekPanel
    from .audio import Transcriber, audio_manager, mono_input
    import numpy as np
    import psutil

    saved = Settings.load()
    temporary = tempfile.TemporaryDirectory(prefix="matek-native-check-")
    os.environ["LOCALAPPDATA"] = temporary.name
    cfg = replace(saved, mode="local", cloud_access=False, persistent_history=False,
                  preset="gaming" if args.benchmark == "synthetic-gpu" else "balanced",
                  speech_policy="full", microphone=not args.benchmark or args.monitoring in {"all", "microphone"},
                  system_audio=bool(args.benchmark) and args.monitoring in {"all", "system"},
                  continuous_screen=bool(args.benchmark), manual_screenshots=True,
                  local_vision=True, language="", whisper_model=str(args.model.resolve()),
                  max_output_tokens=160, speech_output=True, confidence=.4, activation="automatic")
    report = {"frontend": "Clicky PyQt6", "mode": args.benchmark or "native-acceptance",
              "personal_recordings_saved": False, "screenpipe_present": False}
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    manager = MatekManager(cfg, runtime=bool(args.benchmark))
    panel = MatekPanel(manager)
    manager.sig_response_chunk.connect(panel.append_response_chunk)
    manager.sig_response_done.connect(panel.answer_done)
    manager.sig_state_changed.connect(panel.set_state)
    errors = []
    manager.sig_error.connect(errors.append)
    captions = []
    manager.caption.connect(captions.append)

    card = QLabel("MATEK LOCAL TEST CARD\n\nUnity compiler error CS1002: ; expected\n\nint score = 3\n\nThis is synthetic content created for this test.")
    card.setAlignment(Qt.AlignmentFlag.AlignCenter)
    card.setStyleSheet("background:#122238;color:white;font-size:42px;")
    card.setWindowTitle("Matek synthetic acceptance card")
    card.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    card.showFullScreen()
    panel.show()
    workload = None
    if args.benchmark == "synthetic-gpu":
        import sys
        entry = [] if getattr(sys, "frozen", False) else [str(Path(__file__).resolve().parent.parent / "main.py")]
        gpu_report = Path(temporary.name) / "gpu.json"
        workload = subprocess.Popen([sys.executable, *entry, "--gpu-workload", "--seconds", str(args.seconds + 2),
                                     "--output", str(gpu_report)], creationflags=0x08000000,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    samples, gpu_samples, heartbeat = [], [], []
    process = psutil.Process()
    process.cpu_percent()
    sample_stop = threading.Event()
    started = time.monotonic()
    last_tick = [started]
    timer = QTimer()
    def tick():
        now = time.monotonic()
        heartbeat.append((now - last_tick[0]) * 1000)
        last_tick[0] = now
    timer.timeout.connect(tick)
    timer.start(100)

    def sample():
        while not sample_stop.wait(1):
            samples.append((process.cpu_percent(), process.memory_info().rss))
            if len(samples) % 3 == 0:
                try:
                    out = subprocess.check_output([str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/nvidia-smi.exe"),
                        "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                        creationflags=0x08000000, timeout=3).decode().strip().split(",")
                    gpu_samples.append([int(v.strip()) for v in out])
                except Exception:
                    pass
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    initial_size = sum(p.stat().st_size for p in data_dir().glob("*") if p.is_file())

    if args.benchmark:
        manager.start()
        QTimer.singleShot(max(5, min(args.seconds, 600)) * 1000, app.quit)
    else:
        fixture = args.fixture or Path("tests/fixtures/question.wav")
        with wave.open(str(fixture), "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
            assert audio.getframerate() == 16000 and audio.getnchannels() == 1
        recognized = Transcriber(cfg).transcribe(pcm, "microphone")
        report.update(recognized_fixture=recognized.text, confidence=recognized.confidence)
        # Verify the real selected Focusrite stream; raw samples never leave RAM.
        try:
            with audio_manager() as audio:
                device = audio.get_device_info_by_index(saved.mic_device) if saved.mic_device >= 0 else audio.get_default_input_device_info()
                import pyaudiowpatch as pa
                channels = min(2, device["maxInputChannels"])
                rate = int(device["defaultSampleRate"])
                with __import__("contextlib").closing(audio.open(format=pa.paInt16, channels=channels, rate=rate,
                     input=True, input_device_index=device["index"], frames_per_buffer=1024)) as stream:
                    raw = stream.read(rate, exception_on_overflow=False)
                    mono = mono_input(raw, channels, "microphone")
                    report.update(microphone=device["name"], microphone_frames=len(mono),
                                  microphone_rms=float(np.sqrt(np.mean(mono * mono))))
        except Exception as exc:
            report["microphone_error_type"] = type(exc).__name__
        stage = ["general"]
        def begin():
            manager._transcript(manager.generation, recognized)
        def done(answer):
            if not answer:
                return
            if stage[0] == "general":
                report.update(general_answer=answer, general_caption_updates=len(captions))
                stage[0] = "screen"
                # Finish speaking before requesting a fresh synthetic screenshot.
                def next_question():
                    if manager._answer_busy:
                        QTimer.singleShot(100, next_question)
                    else:
                        manager.submit_question("Explain the error shown on this screen.", addressed=True)
                QTimer.singleShot(100, next_question)
            else:
                report["screen_answer"] = answer
                def finish():
                    if manager._answer_busy:
                        QTimer.singleShot(100, finish)
                    else:
                        panel.grab().save(str(args.output.with_suffix(".png")))
                        # Exercise the real offline TTS interruption path using
                        # a synthetic locally transcribed Stop command.
                        from .context import Transcript
                        manager.speech.configure(replace(cfg, speech_output=True))
                        manager.speech.feed("This deliberately long local sentence is spoken only to verify that the companion can stop its offline voice immediately when asked. ")
                        manager.speech.finish()
                        QTimer.singleShot(350, lambda: manager._transcript(manager.generation,
                            Transcript(time.time(), "Stop.", "microphone")))
                        def stopped():
                            report["offline_stop_passed"] = not manager.speech.active and manager._cancel_flag
                            app.quit()
                        QTimer.singleShot(1000, stopped)
                QTimer.singleShot(100, finish)
        manager.sig_response_done.connect(done)
        manager.sig_error.connect(lambda _: QTimer.singleShot(0, app.quit))
        QTimer.singleShot(200, begin)
        QTimer.singleShot(150000, app.quit)
    app.exec()
    sample_stop.set()
    sampler.join(4)
    report.update(seconds=round(time.monotonic() - started, 2), cloud_entries=len(manager.ledger.history()),
                  transcriptions=manager._memory.audio.transcriptions,
                  transcription_seconds=round(manager._memory.audio.transcription_seconds,2),
                  context=manager._memory.engine.inspect(), errors=errors,
                  offline_voice=manager.speech.tts.voice().name() if manager.speech.tts else "unavailable",
                  installed_voice_locales=[v.locale().name() for v in manager.speech.tts.availableVoices()] if manager.speech.tts else [],
                  caption_updates=len(captions),
                  storage_growth_bytes=sum(p.stat().st_size for p in data_dir().glob("*") if p.is_file()) - initial_size)
    if samples:
        report.update(cpu_one_core_mean_percent=round(statistics.mean(s[0] for s in samples),2),
                      cpu_one_core_peak_percent=max(s[0] for s in samples), peak_rss_mb=round(max(s[1] for s in samples)/1024**2,2))
    if heartbeat:
        report.update(ui_heartbeat_p95_ms=round(sorted(heartbeat)[int(.95*(len(heartbeat)-1))],2), ui_heartbeat_max_ms=round(max(heartbeat),2))
    if gpu_samples:
        report.update(gpu_utilization_mean_percent=round(statistics.mean(s[0] for s in gpu_samples),2),
                      gpu_peak_memory_mb=max(s[1] for s in gpu_samples))
    if workload:
        try:
            workload.wait(10)
            report.update(json.loads(gpu_report.read_text(encoding="utf-8")))
        except Exception as exc:
            workload.terminate()
            report["shader_error"] = type(exc).__name__
        report["measurement_limit"] = "Separate synthetic OpenGL shader process, not an actual game or game FPS comparison."
    manager.shutdown()
    card.close()
    panel.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    temporary.cleanup()
    if not args.benchmark:
        assert report.get("general_answer") and report.get("screen_answer") and report["cloud_entries"] == 0, report
    return 0


def gpu_workload():
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader, QOpenGLFunctions_4_1_Core, QOpenGLVertexArrayObject
    from PyQt6.QtGui import QSurfaceFormat
    from PyQt6.QtCore import QTimer
    class Workload(QOpenGLWidget):
        def __init__(self):
            super().__init__()
            fmt = QSurfaceFormat()
            fmt.setVersion(4, 1)
            fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
            fmt.setSwapInterval(0)
            self.setFormat(fmt)
            self.setWindowTitle("Matek synthetic GPU benchmark")
            self.frames = 0
            self.error = ""
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update)
            self.timer.start(1)
        def initializeGL(self):
            self.gl = QOpenGLFunctions_4_1_Core()
            self.gl.initializeOpenGLFunctions()
            self.vao = QOpenGLVertexArrayObject(self)
            self.vao.create()
            self.vao.bind()
            self.program = QOpenGLShaderProgram(self)
            vertex = "#version 330 core\nvoid main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.0-1.0,0,1);}"
            fragment = "#version 330 core\nout vec4 colour; uniform float phase; void main(){vec2 p=gl_FragCoord.xy/700.0;float v=phase;for(int i=0;i<220;i++){p=sin(p.yx*1.012+v);v+=cos(p.x*p.y+float(i)*0.01)*0.005;}colour=vec4(abs(sin(vec3(p,v))),1);}"
            if not (self.program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, vertex) and
                    self.program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, fragment) and self.program.link()):
                self.error = self.program.log()
        def paintGL(self):
            if self.error:
                return
            self.vao.bind()
            self.program.bind()
            self.program.setUniformValue("phase", self.frames * .001)
            self.gl.glDrawArrays(4, 0, 3)
            self.frames += 1
    return Workload()


def run_gpu(seconds, output):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    app = QApplication([])
    workload = gpu_workload()
    workload.showFullScreen()
    QTimer.singleShot(max(5, min(seconds, 600)) * 1000, app.quit)
    app.exec()
    output.write_text(json.dumps({"synthetic_gpu_frames": workload.frames, "shader_error": workload.error}), encoding="utf-8")
