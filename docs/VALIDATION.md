# Validation evidence — 13 October 2026

The current app extends the genuine Clicky/PyQt6 manager and panel. Its native binary is separate from the earlier standalone PySide6 installation. These are measurements on this PC, not guaranteed performance on other hardware.

## Automated checks

`python -m pytest tests -q`: **38 passed**. The tests use deterministic substitute AI providers and local API fixtures, with actual Clicky-derived orchestration and Qt widgets. They cover the ten master-request scenarios plus cloud decline/approval/budget accounting, fragmented speech, code fences, provider errors, privacy, Stop debounce, offline routing and selected conversation history, provider-specific pricing and billable Copilot probe prevention. No paid request was used for these tests.

| Master scenario | Evidence | Limit |
|---|---|---|
| General knowledge | Generated English speech → real local Whisper → detector → Clicky pipeline → Ollama → offline voice/captions | Not a human microphone question |
| Screen question | Real fresh MSS screenshot of own full-screen Unity error test card → local vision answer | No real game/editor task tested |
| Previous screen event | Automated before/after RAM selection and context | No live disappearing game object tested |
| Follow-up | Automated global conversation continuity and unrelated-history exclusion | Semantic quality depends on model |
| Educational video | Transcript-context tests; real WASAPI loopback transcribed the generated audio fixture | No actual lecture/video understanding session tested |
| No idle API costs | Normal/GPU monitoring measurements: zero ledger entries | Cloud providers not exercised with paid keys |
| Routing | Local/hybrid/confirmation/offline tests and actual local answer | Heuristic difficulty classifier |
| Spoken Stop | Actual Windows offline voice interrupted through locally supplied Stop transcript | Stop word itself was synthetic, not a human ASR sample |
| Performance | Actual normal monitoring and separate heavy OpenGL shader process | Synthetic workload, no real game/FPS comparison |
| Privacy | Excluded frame/API filtering and credential tests; real synthetic Bitwarden-window capture blocked, then permitted synthetic capture succeeded | Not perfect detection of every sensitive pixel/utterance |

## Native source results

The generated fixture “What is the meaning of epistemology?” was transcribed exactly, confidence **0.8116**. Ollama returned “Epistemology is the study of knowledge and how it is acquired.” The real test screen answer identified the missing semicolon. Microsoft Hazel Desktop produced **48 caption updates**. Offline Stop passed. The Focusrite input returned 44,100 frames for the microphone stream check. No raw recording or captured desktop image was saved; the optional PNG is a grab of the synthetic companion answer panel.

Separate loopback check: generated fixture recognised through the real system output pipeline, source `system`, confidence **0.7692**, no input errors, no raw recording saved.

Local detailed reports live in ignored `artifacts/native-final-source.json`, `artifacts/loopback.json`, and the packaged/native reports. Real local Polish text answer was also verified in `artifacts/local-polish.json`; automatic-language capability is configured; live Polish ASR and natural Polish TTS are not verified. Only an `en_GB` offline Windows voice is installed.

## Resource measurements

CPU here uses psutil's **100% = one logical CPU core** convention. The i7-8700K has twelve logical cores. RSS is for the companion process, excluding Ollama and the separate GPU workload. GPU utilisation/memory is for the entire device, not attributable solely to Matek. No personal screen/audio data was written by the benchmark. A 100 ms Qt heartbeat checks responsiveness.

| Source measurement | Duration | Mean CPU (one core) | Peak RSS | UI p95 / maximum | Storage growth |
|---|---:|---:|---:|---:|---:|
| Screen monitoring only | 15 s | 4.26% | 144.52 MiB | 125 / 125 ms | 0 bytes |
| Microphone + screen | 15 s | 6.11% | 146.72 MiB | 125 / 140 ms | 0 bytes |
| System audio + screen | 15 s | 4.63% | 146.37 MiB | 125 / 125 ms | 0 bytes |
| Normal, all monitoring, separate from GPU run | 60 s | 56.97% | 505.52 MiB | 110 / 125 ms | 0 bytes |
| Gaming mode + separate shader workload | 60 s | 24.34% | 374.03 MiB | 110 / 203 ms | 0 bytes |

Normal's first minute included one local ASR operation/model initialization taking 16.22 seconds and a 214.2% one-core peak. It is not a steady-state silence baseline. Gaming included three local ASR operations totalling 6.09 seconds; its synthetic GPU process rendered 11,128 frames, averaged 86.79% total GPU utilisation, and had no shader errors. Gaming mode unloaded the prior GPU-resident model; measured total GPU memory peaked at 1,195 MiB, versus about 5,200 MiB during local vision inference. These short observations do not establish long-term battery/thermal behaviour or a real-game FPS guarantee.

## Packaging and external limits

PyInstaller builds an onedir MatekScreenCompanion executable with PyQt6, excluding PySide6; the downloaded multilingual model is copied alongside it. Source/packaged smoke tests isolate app data. Final packaged native acceptance exited 0: exact English fixture confidence 0.8116, correct general/synthetic-screen answers, 48 offline caption updates, Stop passed, no errors and zero cloud entries. The final smoke exited 0. A second normal launch exited 0 without opening a duplicate instance. The original local installation is kept as a backup. Settings, optional Q/A history, vault keys and live zero-cost ledger are preserved when switching the shortcut.

Screenpipe is absent from localhost:3030. Its live recording/history/retention/storage/game overhead are unverified; adapter fixture tests do not establish those results. No real paid cloud calls, commercial distribution or invasive game hooks are part of this work. See [Screenpipe](SCREENPIPE.md) and [dependency licence notes](THIRD_PARTY.md).
