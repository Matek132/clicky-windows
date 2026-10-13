# Matek Screen Companion — Clicky Windows fork

A local Windows companion built by extending Clicky's actual Python/PyQt6 manager, panel, providers and pointing interface. Ask general questions, ask about the screen or recent audio, and continue a conversation without leaving the active application. Ollama handles reasoning; local faster-whisper handles microphone/WASAPI speech; Windows SAPI handles offline spoken answers. No paid key is needed in Local Only mode.

## Use the local app

Launch `dist/MatekScreenCompanion/MatekScreenCompanion.exe`, or the **Matek Screen Companion** desktop shortcut configured on this PC. Keep the entire executable folder together.

- Hover over the small animated presence to type a question or open **Settings**.
- In automatic listening mode, natural microphone questions receive short written answers. With the saved **wake** speech policy, say **“Matek, what is gravity?”** for a spoken answer. Select **full** in Settings → Voice to speak every answer.
- **Ctrl+Win** is the original manual voice capture; tap then speak, or hold and release. **Esc** / spoken **Stop** cancels generation and voice. **Ctrl+Alt+P** pauses all Matek monitoring; **Ctrl+Alt+O** shows the panel.
- Enable/disable mic, system audio, screen awareness, history and cloud access independently. System audio helps answer questions about a lecture; answering questions heard in computer audio is a separate option and defaults off.
- Settings → Intelligence selects Local Only, Hybrid or Cloud Preferred, model, optional web access and performance mode. **Gaming** reduces screen observation and uses CPU local inference, or authorised cloud reasoning; **Offline** forces local reasoning and disables web research.
- Original Clicky pointing, annotation/cursor mode, document attachments and tray controls remain available. The overlay uses ordinary Windows windows; exclusive-fullscreen games may hide it.

The saved personal profile enables Focusrite microphone listening, screen/system awareness and local vision. Fresh installs default monitoring off until enabled. The app retains up to 120 seconds of bounded screenshots/transcripts in RAM. It does not save raw microphone/loopback recordings or screen captures by default. Optional conversation history saves answered questions and answers under `%LOCALAPPDATA%/MatekScreenCompanion`; History can erase it. New API/OAuth credentials use the Windows vault (legacy Clicky environment/token files remain readable for compatibility); usage records contain numeric accounting, not transcripts. Visible excluded windows block monitor capture, with additional credential-pattern filters; this is not perfect semantic detection of every secret.

## Models and current information

The installed `qwen2.5vl:3b` is a small local vision/text model, not a guarantee of correct answers on every subject. General questions do not attach screenshots. Follow-ups use selected conversation history. Complex topics can use a stronger installed model or an explicitly authorised cloud provider later.

Models do not train themselves on new facts. Replacing a model is optional; current questions can use event-driven web research when enabled. Internet research is not offline and sends the search question to search/page services. It is disabled in the current local profile. Cloud answers require permission and budget checks. Unknown provider/model pricing blocks a paid request until configured in the local pricing file (`providers` overrides are keyed by provider/endpoint); incomplete usage retains its reservation. Provider billing and local estimates may differ, so configure provider-side limits as well.

Multilingual Whisper **base** supports English/Polish automatic recognition. The English generated-speech path and real Focusrite stream were tested. A local Polish text answer was tested; Polish live recognition remains unverified on this PC. Microsoft Hazel British English is the installed offline voice; no native Polish Windows voice is currently installed. Polish text can be requested, but natural Polish TTS needs a suitable offline voice.

## Optional long-term memory

[Screenpipe setup and privacy](docs/SCREENPIPE.md) describes the independent local HTTP adapter. Screenpipe is optional and is not installed/bundled here. With it disabled or unavailable, two-minute RAM memory and general questions still work. Its current licence needs a separate review before commercial embedding/distribution. [Dependency and licence review](docs/THIRD_PARTY.md) also covers PyQt and model notices.

## Development and local verification

Python 3.11 is used on this PC. Create a venv, install `requirements.txt` plus `pytest`/`pyinstaller`, and download `models/whisper-base` using `scripts/download_model.ps1`. Install Ollama and pull/select a compatible local vision model. Install Tesseract for optional local OCR; screen images work without it.

```powershell
python -m pytest tests -q
python main.py --smoke-test --output artifacts/source-smoke.json
python scripts/native_matek_check.py
python main.py --benchmark normal --seconds 60 --output artifacts/normal.json
python main.py --benchmark synthetic-gpu --seconds 60 --output artifacts/gpu.json
powershell -ExecutionPolicy Bypass -File scripts/build_native.ps1
```

The native check uses generated speech and its own synthetic full-screen test card, isolates application data, tests real local ASR/Ollama/vision/TTS/Stop, and samples the configured microphone without saving audio. The GPU benchmark launches its own shader process and is **not a real game benchmark**. Read [validation evidence and limits](docs/VALIDATION.md); do not treat mocked acceptance tests as live human voice/game/Screenpipe evidence.

Original Clicky licence/attribution is preserved. See [upstream documentation](docs/CLICKY_UPSTREAM.md) for historical Clicky features; its old defaults differ from this fork. `matek-desktop/` is retained legacy standalone source and is not the entrypoint for the new Clicky-based app.
