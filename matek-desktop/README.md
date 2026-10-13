# Local Matek desktop build

This folder contains the source of the locally installed Matek desktop companion, including its PySide6 mascot/hover interface, hands-free microphone, offline Windows speech, local Ollama answers and optional Screenpipe API adapter. The upstream PyQt Clicky frontend remains at the repository root. Run one frontend at a time to avoid duplicate perception. They use the same original HTTP adapter; no Screenpipe application code is bundled.

On the owner's machine, the installed executable is `D:\MateksHub\Companion\dist\MatekScreenCompanion\MatekScreenCompanion.exe`; existing desktop/Start Menu shortcuts launch it. See [local memory settings and remaining verification](docs/LOCAL_MEMORY.md).

To run this source separately, use Python 3.11–3.13 on Windows, create `.venv` in this folder, install `requirements.txt`, download the offline speech model with `scripts/download_model.py`, install/start Ollama and select an installed local model in the UI. Run `python main.py`. Settings and saved history use the existing `%LOCALAPPDATA%\MatekScreenCompanion` folder; API tokens use Windows keyring. New installs start with capture/cloud permissions off. Screenpipe is a separate optional service; RAM memory works without it.

Run `python -m pytest -q` for tests. The generated speech fixture and downloaded ASR model are deliberately not committed; offline ASR integration tests skip until those fixtures/models exist. `scripts/build_windows.bat` builds a portable executable and runs packaged startup, offline voice, and (when assets exist) ASR checks. No personal settings, captured desktop/audio, history databases, API keys, model weights, or executable bundles are committed here.

Preserve the repository's Clicky licence/attribution and review [third-party notices](THIRD_PARTY.md) before distribution. This desktop entry point is not a migration of every upstream tutor/drawing feature; the original Clicky entry point remains available.
