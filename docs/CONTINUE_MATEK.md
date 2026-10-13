# Matek continuation checkpoint — 13 October 2026

## Stop instruction and boundary

The user explicitly requested: "stop at the safest waypoint and make sure you know what to do when asked to continue". Work paused before building, replacing, or launching a new installed application. Do not resume implementation until the user asks to continue. This document and a local Git checkpoint preserve the unfinished source work. No new deployment or GitHub push is part of this pause.

The master request is in `C:\Users\mtk\.codex\attachments\ec63731b-5eb0-467b-b13e-f6c858600488\Pasted text.txt`. Read it when resuming. It requires extending actual Clicky, universal English/Polish voice, short answers, bounded local memory, offline operation, permission/budget controls, privacy, efficient gaming operation, packaging, and ten acceptance scenarios. Earlier optional Screenpipe requirements also apply.

## Workspace and product identity

- Fork checkout: `D:\MateksHub\Companion\clicky-windows`.
- Origin: https://github.com/Matek132/clicky-windows ; branch: `matek-screenpipe-memory`.
- Last pushed commit before this checkpoint: `4766986`.
- Existing draft PR: https://github.com/Matek132/clicky-windows/pull/1 (already attached to the chat). Its current description covers the older integration; rewrite only after the native implementation is ready.
- Existing installed executable remains `D:\MateksHub\Companion\dist\MatekScreenCompanion\MatekScreenCompanion.exe`. It is the older standalone PySide6 version. It has not been replaced by the new Clicky version. No Matek or Python process was present at the pause process check; do not claim it is running.
- Desktop shortcut remains `C:\Users\mtk\Desktop\Matek Screen Companion.lnk`. Keep existing app/data available until the replacement is validated.
- New source is genuinely Clicky/PyQt6: `MatekManager` subclasses `CompanionManager`; `MatekPanel` subclasses `CompanionPanel`; original cursor/pointing/providers are retained.
- Old separate source in `matek-desktop/` and parent `companion/` is currently retained. Do not remove backups during the pause.

## Implemented source work (unfinished)

`main.py` now uses the Clicky-derived Matek manager/panel. `companion_manager.py` factors the existing answer pipeline into `_answer_question` and adds capture, prompt, history, and classification hooks. The new `matek/` package adds local perception, bounded memory, question detection, routing, guarded providers, cost ledger, speech, compact hover UI, settings, privacy, and optional history.

Key behavior:

- Local Ollama by default, no paid API requirement. Local model defaults to `qwen2.5vl:3b`; remote Ollama models are rejected.
- CPU/int8 local faster-whisper, strongest Focusrite stereo channel, independent system loopback, long-pause/partial question handling, bounded raw audio chunks. Focusrite Analogue 1 + 2 is the user's confirmed microphone.
- System audio transcribes continuous bounded chunks; unfinished microphone questions can wait longer. Manual capture release explicitly flushes its segment.
- Offline Windows speech and word captions; full/summary/text/auto/wake policies. Earlier user preference is ordinary questions displayed and "Matek..." questions spoken.
- Screen/OCR/transcript RAM retention at most 120 seconds; no routine raw recording written to disk. Optional answered Q/A history is separate from the RAM buffer.
- Optional Screenpipe loopback HTTP adapter, no copied Screenpipe source; per-source ownership avoids duplicate screen/system capture. Disabled or unavailable falls back to RAM.
- Cloud scope requires permission, optional confirmation, budget reservation, bounded output, duplicate prevention, cancellation, usage settlement where exposed. Failures/interrupted streams conservatively retain the estimate. Unknown pricing fails closed. No real paid call has been made during development.
- General questions use general prompts; screen references trigger context and existing Clicky pointing flow. Global history supports follow-ups.
- Unified privacy, memory, intelligence, voice, budget, interface settings; Windows keyring for new API-key edits. Existing legacy environment compatibility remains and needs review.
- Hover typing/settings, copy/history/stop/pause/resize, original cursor alternative, autostart helper, pause/show shortcuts, isolated source smoke settings.

## Verified evidence and limits

Last completed test suite: **28 passing tests**, including the original adapter tests and `tests/test_matek_acceptance.py`. These cover actual subclass pipeline with mocked providers, general/screen/past/follow-up/lecture scenarios, idle no dispatch, cloud permission/budget controls, Stop, gaming configuration/RAM bounds, privacy exclusion, and panel controls. Some tests use synthetic screens or text and are not live-human acceptance evidence.

- Source startup/close smoke passed: `D:\MateksHub\Companion\artifacts\clicky-matek-source-smoke.json` reports exit 0, Clicky PyQt6, MatekManager.
- Real local ASR/Ollama/offline voice source check passed: `D:\MateksHub\Companion\artifacts\clicky-matek-native.json`. Generated English fixture recognized "What does this symbol mean?" with confidence 0.7621. The subsequent explicit general question returned "Epistemology is the study of knowledge and how it is acquired." Microsoft Hazel Desktop produced 12 caption updates; cloud entries 0; measured 13.89 seconds including generation/speech.
- Synthetic app panel screenshot: `D:\MateksHub\Companion\artifacts\clicky-matek-answer.png`.
- The ASR evidence uses generated/recorded speech, not a live human speaking into Focusrite.
- Latest code-fence speech buffering change has not had a dedicated native validation. Do not generalize the earlier speech check to that change.
- New native executable has **not** been built, installed, or fully benchmarked.
- Screenpipe is not installed or serving localhost:3030. Live history, capture ownership, retention, and gaming with Screenpipe remain unverified.
- Earlier standalone CPU/RAM figures are not measurements of the new native implementation.
- Polish ASR and available Polish offline TTS are not yet verified.

## Local runtime and saved profile

- Shared Python runtime: `D:\MateksHub\Companion\.venv\Scripts\python.exe` (3.11.9). In the fork use `..\.venv\Scripts\python.exe`.
- PyQt6 and PySide6 both exist in that venv. Exclude PySide6 from the new Clicky PyInstaller build.
- Ollama server defaults to 127.0.0.1:11434; `qwen2.5vl:3b` installed. GPU: GTX 1070; CPU i7-8700K, 16 GB RAM, display 2560x1440.
- Multilingual model downloaded successfully to `D:\MateksHub\Companion\clicky-windows\models\whisper-base`. Model files are intentionally Git-ignored.
- Previous English model exists in parent `models/whisper-tiny.en` and stable distribution. New Settings default still points to tiny.en; switch final profile/default to multilingual base/auto after validation.
- Tesseract: `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- Settings/data: `%LOCALAPPDATA%\MatekScreenCompanion` (settings.json, optional history.sqlite3, numeric usage.sqlite3, type-only events.log). Keys belong in Windows vault, never Git.
- Previous profile: local/cloud off; microphone/system/screen/manual screenshots enabled; automatic questions, confidence .45, debounce 2, noise floor 50; retention 120; local vision on; output 160; display 60; optional Q/A history enabled.
- A source smoke previously overwrote preferences via model refresh. Preferences were restored and smoke now isolates LOCALAPPDATA in a temporary directory. Verify settings before installation and keep every smoke/integration test isolated. Do not erase user history.

## Resume in this order

1. Read this checkpoint and master prompt; inspect Git status/diff. Keep the genuine Clicky subclass approach. Re-run source compilation and the current suite once needed for new edits.
2. Fix known lifecycle issues: inherited answer errors are caught internally and can leave a speech future hanging; ensure terminal error/empty-answer completion. Make `_scheduled` reset even if cancelled before task entry; prevent stale speech callbacks from completing a later request; bound provider-pool retirement waits. Verify Stop during actual speech and queued cancellation.
3. Fix summary speech: current chunk.split word counting can count token fragments and truncate midword. Buffer complete phrases/words and finish through the Qt main thread. Validate streaming code-fence suppression, replay/mute, manual release flush, and continuous system audio.
4. Finish contextual details: avoid a stale "no screenshot" note when fresh capture is subsequently available; capture selected monitors directly instead of all monitors before filtering; show citations/source links and clear freshness limitations. Confirm explicit web opt-in and strict offline mode. Improve Polish/follow-up/style commands where the prompt requires them.
5. Polish minimal presence/hover interface, optionally animated Clicky triangle, visible opt-in nonverbal suggestions, saved geometry. Preserve original pointing/cursor alternative. Add the shared Windows singleton mutex `Local\MatekScreenCompanion`, useful startup diagnostics, and clean hotkey shutdown. Exclude settings windows from capture too.
6. Make `scripts/native_matek_check.py` portable; tests currently rely on parent fixture/artifact paths. Add meaningful tests for the issues above. Validate actual capture using an app-owned synthetic test card, not saved personal desktop imagery.
7. Validate English/Polish multilingual ASR, offline voice availability, and live mic pipeline as far as safely possible. If Polish voice is absent, report it accurately rather than claiming it works.
8. Benchmark native CPU/RAM/storage and gaming behavior. A synthetic GPU workload must be labelled synthetic; actual game performance remains separate. Record GPU utilization, UI heartbeat/frame timing, and inference effects. Gaming CPU-only requests must also unload any previously resident Ollama GPU model (current config alone may leave it resident for minutes).
9. Update `clicky.spec` to build MatekScreenCompanion using actual Clicky entrypoint, include pricing/knowledge/Qt/audio/keyring assets and required metadata, exclude PySide6. Isolate build PATH to `.venv\Scripts;System32;Windows` to avoid unrelated Poppler/ICU DLL contamination. Include multilingual base model and licence notices in distribution. Use absolute PowerShell paths in helpers if PATH is restricted.
10. Test the new packaged app independently with isolated data before replacing the existing local installation. Preserve user settings/history/vault, then update final whisper profile and shortcuts. If stopping the old process, match its exact executable path; its shutdown can overwrite settings, so account for ordering. Launch and validate visible native UI, singleton, local answer/voice/stop, and zero cloud usage.
11. Update README, licence notes, acceptance evidence, and limits honestly. Only remove obsolete fork `matek-desktop/` after native parity and package verification; preserve parent backup. Verify absolute target containment before any recursive Windows delete/move.
12. Commit/push validated final work to the existing branch and update draft PR #1 to describe the actual final native implementation. Do not stop at a PR: the user wants a working local app.

## Screenpipe and GitHub constraints

Screenpipe's current upstream licence is Commercial License, not MIT: https://github.com/screenpipe/screenpipe/blob/main/LICENSE.md . Personal/noncommercial use differs from commercial embedding/distribution; review licensor terms before shipping commercially. Keep it a separate optional service. Existing docs: `docs/SCREENPIPE.md` and old standalone local-memory docs.

Adapter uses documented local health/search/frame endpoints, loopback-only URL validation, redirects disabled, environment proxies disabled, bounded responses/timeouts, include_cloud=false, metadata/privacy filters before selected frame retrieval, and explicit retention configuration. Screenpipe should own screen/system audio while Matek owns mic. Adapter pause does not stop an independently running recorder. Live API behavior still needs validation.

GitHub credentials cannot push `.github/workflows` (workflow scope absent). An example workflow is already in `docs/memory-tests.workflow.yml.example`. Do not retry that rejected workflow push or invent an approval requirement. The existing PR is a draft.

## Completion standard

Resume autonomously when asked. Finish safe fixes, appropriate tests, honest measurements, packaging, and the working local Clicky-based installation. No cloud subscription is needed. Do not claim the full master prompt, live Screenpipe, human microphone, Polish speech, or real gaming is verified without evidence.
