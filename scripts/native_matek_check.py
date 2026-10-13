"""Portable generated-speech/native Ollama/vision/TTS check; no personal recordings."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
import os
os.chdir(root)
from matek.diagnostics import run
run(["--native-check", *sys.argv[1:]] if sys.argv[1:] else
    ["--native-check", "--output", str(root / "artifacts/native-check.json")])
