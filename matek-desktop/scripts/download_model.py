"""Explicit one-time free model download. The application never downloads models."""
from pathlib import Path
from huggingface_hub import snapshot_download

if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "models" / "whisper-tiny.en"
    snapshot_download("Systran/faster-whisper-tiny.en", local_dir=target,
                      allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary.txt", "vocabulary.json"])
    print("Offline transcription model ready:", target)
