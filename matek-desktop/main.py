import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="Matek Screen Companion")
    parser.add_argument("--smoke-test", action="store_true", help="Start safe UI and exit after 700ms")
    parser.add_argument("--diagnose", action="store_true", help="Print local dependencies; does not capture or contact AI")
    parser.add_argument("--transcribe-file", type=Path, help="Locally transcribe a 16kHz mono PCM16 WAV; no capture or cloud use")
    parser.add_argument("--output", type=Path, help="Write transcription/diagnostics JSON for windowed executable checks")
    parser.add_argument("--local-test-image", type=Path, help="Run a free local vision diagnostic against an explicit image")
    parser.add_argument("--speech-test", action="store_true", help="Speak a known test sentence locally and verify captions")
    args = parser.parse_args()
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    os.chdir(root)
    if args.speech_test:
        import json
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        from companion.config import Settings
        from companion.speech import SpokenAnswer
        app = QApplication([])
        speech = SpokenAnswer(Settings())
        captions, errors = [], []
        speech.text_changed.connect(captions.append)
        speech.error.connect(errors.append)
        speech.completed.connect(app.quit)
        text = "Put one torch in the centre. Surround it with eight iron nuggets."
        def begin():
            speech.feed(text)
            speech.finish()
        QTimer.singleShot(100, begin)
        QTimer.singleShot(15000, app.quit)
        app.exec()
        success = bool(captions) and captions[-1] == text and not errors
        result = json.dumps({"success": success, "caption_updates": len(captions),
                             "voice": speech.tts.voice().name() if speech.tts else None,
                             "errors": errors, "cloud_requests": 0}, indent=2)
        if args.output:
            args.output.write_text(result, encoding="utf-8")
        else:
            print(result)
        return 0 if success else 1
    if args.local_test_image:
        from dataclasses import replace
        from io import BytesIO
        import json
        import tempfile
        import threading
        import time
        from PIL import Image
        from companion.config import Settings
        from companion.context import ContextEngine, Frame
        from companion.controller import RequestController
        from companion.costs import CostLedger
        from companion.providers import OllamaProvider
        cfg = replace(Settings.load(), mode="local", cloud_access=False, local_vision=True,
                      manual_screenshots=True, max_output_tokens=180)
        image = Image.open(args.local_test_image).convert("RGB")
        image.thumbnail((cfg.image_max_side, cfg.image_max_side))
        encoded = BytesIO()
        image.save(encoded, format="JPEG", quality=85)
        engine = ContextEngine(cfg)
        engine.add_frame(Frame(time.time(), encoded.getvalue(), "Matek diagnostic", "Explicit test image"))
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="matek-local-test-") as directory:
            ledger = CostLedger(Path(directory) / "usage.db")
            controller = RequestController(ledger)
            prepared = controller.prepare(engine.select("Read the error code shown in the image and explain its meaning in C# and its fix in two sentences."), cfg)
            chunks = []
            controller.execute(prepared, OllamaProvider(), threading.Event(), chunks.append)
            result = json.dumps({"answer": "".join(chunks), "model": cfg.local_model,
                                 "seconds": round(time.monotonic() - started, 2),
                                 "cloud_ledger_entries": len(ledger.history())}, indent=2)
        if args.output:
            args.output.write_text(result, encoding="utf-8")
        else:
            print(result)
        return 0
    if args.transcribe_file:
        import json
        import wave
        from companion.config import Settings
        from companion.audio import Transcriber
        with wave.open(str(args.transcribe_file), "rb") as audio:
            if audio.getframerate() != 16000 or audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                parser.error("WAV must be 16kHz mono PCM16")
            if audio.getnframes() > 16000 * 60:
                parser.error("WAV diagnostic is limited to 60 seconds")
            pcm = audio.readframes(audio.getnframes())
        snippet = Transcriber(Settings()).transcribe(pcm, "microphone")
        result = json.dumps({"text": snippet.text, "confidence": snippet.confidence, "cloud_requests": 0}, indent=2)
        if args.output:
            args.output.write_text(result, encoding="utf-8")
        else:
            print(result)
        return 0
    if args.diagnose:
        from companion.diagnostics import diagnose
        return diagnose()
    if args.smoke_test:
        # Isolate the smoke test from the user's saved preferences and budgets.
        import tempfile
        with tempfile.TemporaryDirectory(prefix="matek-smoke-") as directory:
            os.environ["LOCALAPPDATA"] = directory
            from companion.app import run
            result = run(smoke=True)
            if args.output:
                import json
                args.output.write_text(json.dumps({"smoke_exit": result}), encoding="utf-8")
            return result
    import logging
    from logging.handlers import RotatingFileHandler
    from companion.config import data_dir
    handler = RotatingFileHandler(data_dir() / "events.log", maxBytes=256000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter('{"at":"%(asctime)s","level":"%(levelname)s","event":"%(message)s"}'))
    logging.getLogger("matek").addHandler(handler)
    logging.getLogger("matek").setLevel(logging.INFO)
    from companion.app import run
    return run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Startup failures must not strand a windowed executable behind a modal bootloader error.
        # Store stack locations/type only; no exception bodies, credentials or prompt text.
        import json
        import traceback
        from companion.config import data_dir
        report = {"error_type": type(exc).__name__, "missing_module": getattr(exc, "name", None),
                  "stack": [{"file": entry.filename, "line": entry.lineno, "function": entry.name}
                            for entry in traceback.extract_tb(exc.__traceback__)]}
        target = data_dir() / "startup-error.json"
        if "--output" in sys.argv:
            target = Path(sys.argv[sys.argv.index("--output") + 1])
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        sys.exit(1)
