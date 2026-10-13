# Matek continuation state — 13 October 2026

The earlier pause ended when the user said “continue”. The genuine Clicky-based local application is now built, installed through updated shortcuts, launched and verified. Do not rebuild the old separate standalone implementation by mistake.

## Current local setup

- Checkout: `D:\MateksHub\Companion\clicky-windows`; branch `matek-screenpipe-memory`; origin https://github.com/Matek132/clicky-windows . Read `git log` for the current saved source commit.
- Native executable: `D:\MateksHub\Companion\clicky-windows\dist\MatekScreenCompanion\MatekScreenCompanion.exe`.
- Desktop and Start Menu shortcuts **Matek Screen Companion** point to that native executable.
- Last verified running PID: **18300**; window title **Matek Screen Companion · Clicky Windows**. PIDs are temporary; verify the exact executable path before stopping anything.
- Actual inheritance: `MatekManager(CompanionManager)` and `MatekPanel(CompanionPanel)`, using Clicky's real question/provider/pointing pipeline and PyQt6. This is no longer the old separate PySide6 interface.
- Local profile: Ollama `qwen2.5vl:3b`, Local Only, cloud off, web off, Focusrite default microphone enabled, automatic activation, speech policy `wake`, screen/system monitoring on, RAM memory backend, multilingual `models/whisper-base`, language auto. Say “Matek…” for speech; full voice policy can speak every question.
- Existing user history/preferences/vault are preserved. Shared data is `%LOCALAPPDATA%\MatekScreenCompanion`. Settings before the switch are backed up there as `settings-before-clicky-native-20261013.json`.
- Previous standalone binary remains `D:\MateksHub\Companion\dist\MatekScreenCompanion\MatekScreenCompanion.exe`; it is a backup and is not running. Restore its old settings backup before rollback because its speech-model folder differs. Legacy fork source `matek-desktop/` is retained and is not the native entrypoint.
- Shared Python 3.11 venv is `D:\MateksHub\Companion\.venv`. The native build excludes PySide6, includes multilingual base model, and isolates PATH to avoid incompatible DLLs. Use `scripts/build_native.ps1`.
- Existing draft PR #1: https://github.com/Matek132/clicky-windows/pull/1 . Keep work on the existing branch/PR when continuing repository changes.

## Completed verification

- **38 automated tests pass**. Source compilation and diff checks passed.
- Packaged smoke and real native acceptance exited 0. Generated English speech was recognised exactly with confidence 0.8116 and passed through the detector/Clicky pipeline to real Ollama. General epistemology answer and actual synthetic Unity screen/missing-semicolon answer were correct. Windows Hazel voice produced 48 captions; real offline Stop passed; zero cloud entries and no native errors.
- Focusrite stream opened and delivered audio frames. This does not establish recognition of a human speaking into it at their usual level.
- Actual WASAPI loopback recognised generated fixture audio locally (confidence 0.7692). No raw recordings were saved.
- Real Windows privacy test blocked an own synthetic Bitwarden-titled window, retained zero excluded frames, then allowed a permitted synthetic frame. No pixels saved or cloud calls.
- Actual local Polish text answer worked. Polish human ASR and natural Polish voice remain unverified; only British English Hazel is installed.
- Normal and separate synthetic GPU-workload resource checks were performed. GPU workload averaged 86.79% utilisation, no shader errors, and the companion remained responsive; gaming unload released prior model GPU memory. This is not an actual game/FPS benchmark. First-minute normal CPU included ASR/model initialization; report exact values/limits from `docs/VALIDATION.md` rather than claiming negligible idle cost.
- Singleton check passed: another normal launch exited 0 and left one native instance.
- Live usage ledger was still empty after installation. No real paid AI call was made.

Detailed reports are in ignored `artifacts/`: `packaged-native.json`, `packaged-final-smoke.json`, `native-final-source.json`, `loopback.json`, `privacy-native.json`, `local-polish.json`, `benchmark-normal-isolated.json`, `benchmark-gpu.json`. Synthetic panel PNGs contain only generated content. Do not save personal desktop/audio to reproduce tests.

## Important implementation decisions

- Speech messages carry playback tokens and main-thread futures; cancelled/old chunks cannot attach to later speech. Summary processing preserves words across model-token fragments. Code fences are suppressed for speech.
- Stop bypasses question debounce and cancels generation/TTS. Manual release flushes audio; wake name can arm the next question; unfinished questions wait for continuation. Microphone and loopback capture are separate and raw queues bounded.
- General questions avoid screenshots and unrelated conversation history. Follow-ups select recent conversation. Captured content is untrusted evidence, never commands. Current facts need enabled event-driven web research.
- All inference providers are wrapped by the request scope/budget guard. SDK retries/probes are constrained; Copilot model discovery does not issue chat probes. New Copilot OAuth tokens and API keys use the vault; legacy Clicky token/env files remain readable for compatibility. Known OpenAI prices are not reused for other providers. Unknown provider/model prices require explicit local `providers` configuration before paid use.
- Selected-monitor capture checks privacy before and after capture; settings/credentials windows and known sensitive text patterns are filtered. These controls do not recognise every possible secret.
- Gaming reduces capture and unloads GPU model residency, then requests CPU local inference unless cloud is separately authorised. Offline preset disables cloud/web. Optional Screenpipe owns healthy screen/system sources; Matek owns microphone.

## External or optional work left

1. Screenpipe is not installed/listening on localhost:3030. Optional adapter fixture tests pass, but live persistent history, retention cleanup, disk growth and gaming overhead have not been tested. Leave RAM backend unless the user wants that separate service set up.
2. If requested, add/verify a natural offline Polish voice and test actual Polish human microphone speech. Do not claim that English Hazel provides natural Polish pronunciation.
3. Actual game-specific performance/FPS and exclusive-fullscreen overlay behaviour need a chosen game/session. Do not label the synthetic shader test as real gaming evidence.
4. Real paid provider validation remains future work requiring the user's cloud permission/key/budget; avoid spending merely to complete tests. Unknown pricing deliberately fails closed.
5. Commercial distribution needs dependency/model/licence review: original Clicky MIT attribution remains; PyQt has GPL/commercial terms; current Screenpipe Commercial License restricts commercial embedding/distribution. No Screenpipe code/binary is bundled.

The full master request remains in `C:\Users\mtk\.codex\attachments\ec63731b-5eb0-467b-b13e-f6c858600488\Pasted text.txt`. README and `docs/VALIDATION.md` describe the actual final behavior and evidence. The GitHub credential lacks workflow scope; retain the example CI file rather than pushing a new active workflow. Preserve user preferences and history during later fixes, and run diagnostic/smoke tests with isolated app data.
