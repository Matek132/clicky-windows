# Optional Screenpipe memory

Implemented in the Clicky fork. Clicky retains microphone activation, STT, reasoning providers, voice playback, UI, drawing and pointing. Screenpipe is a separately installed optional recording/search service, not a reasoning provider. No Screenpipe code or binary is bundled.

Open Tray → Setup & Diagnostics → Local memory / Screenpipe. Both screen and audio history permissions default off. Enable screen memory for bounded two-minute RAM screenshots sampled every five seconds; enable Screenpipe to retrieve longer history. Changing these settings clears the RAM buffer. General questions do not query history or attach screenshots.

## Service setup

Install a Screenpipe version whose licence covers your intended use. Follow its official local recorder setup. Bind its API to loopback (normally port 3030), enable local API authentication, and provide `SCREENPIPE_LOCAL_API_KEY` in Clicky's launch environment. Do not put the key into the URL, source control, screenshots, or benchmark reports. The adapter fails to RAM if this key is absent. The UI saves non-secret settings under `%LOCALAPPDATA%/Clicky/memory.json`; first-launch `.env` defaults are also supported.

Configure Screenpipe recording to own **screen and system audio only**, leaving microphone activation and transcription to Clicky. This fork does not implement a second continuous system-audio recorder. Stop any other companion instance that continuously captures screen/system audio when evaluating Screenpipe. Do not leave the previous standalone Matek recorder running alongside it. Screenpipe must report a healthy vision recorder before fallback screen capture is suspended; health is checked every 15 seconds. A transition can overlap by one polling interval; there is no cross-process capture lease API here. Clicky's explicit pointing queries can still take a fresh screenshot because historical coordinates cannot safely point on today's desktop.

Use Screenpipe's recording exclusion controls for password managers, banking, private browsers, credentials, and sensitive apps. Matek's comma-separated filters are additional retrieval/RAM active-window guards; they do **not** erase or prevent Screenpipe's independent recording. Active-window guards cannot reliably detect every sensitive background window in a whole-monitor RAM image. Enable recorder redaction/encryption where supported, restrict the storage folder with Windows user permissions, and keep firewall access loopback only. Persistent Screenpipe recordings may include raw screen/audio, unlike the RAM fallback. Turning off the adapter does not stop Screenpipe or delete its files.

Set maximum history days in the dialog. Queries are clamped to this limit immediately. To apply physical storage retention to Screenpipe, save settings, reopen the dialog and explicitly click the retention-policy button; Screenpipe then owns cleanup. The adapter neither directly edits its database nor deletes files. Storage retention is not configured until the service accepts that request. Screenpipe plan/version history restrictions may impose a shorter available window.

## Retrieval

Screen/app/activity questions and audio questions select permitted sources locally. Numeric seconds/minutes/hours/days, “ago”, today, yesterday and last week produce bounded ISO timestamps. Unsupported time wording falls back to two minutes; it is not a full natural-language date parser. At most 30 metadata rows, eight selected evidence excerpts, and three downscaled images enter a request. Excluded metadata is filtered before pixels are fetched by frame ID. Images may be unavailable; OCR remains usable. Server file paths are never opened. Cloud search is explicitly false; responses are bounded to 8 MiB, HTTP timeouts to three seconds per request, and proxies/redirects are disabled. Local memory requires no paid AI key. Reasoning still follows Clicky's selected provider and existing authorization behavior.

The RAM fallback holds at most 100 entries / 32 MiB / 120 seconds. It includes permitted recent Clicky microphone transcripts and screen images; **system audio history requires Screenpipe**. There are no persistent fallback recordings. Questions outside retained history receive an explicit missing-history note, not invented evidence. Historical images never drive the pointing engine. Captured text is untrusted evidence, not instructions.

## Testing and benchmarks

Run `python -m pytest tests -q` with pytest installed. Adapter tests use deterministic local API fixtures; they are not evidence that a real Screenpipe recorder worked on this PC. `python -m compileall -q memory_backend.py companion_manager.py ui/memory_dialog.py` checks syntax. Run the application with its normal requirements to verify native UI and provider behavior.

Install `psutil` for the read-only measurement script:

```powershell
python scripts/benchmark_memory.py --mode normal --seconds 300 --output normal.json
# Start your actual game first and use the same capture/model settings:
python scripts/benchmark_memory.py --mode gaming --seconds 300 --output gaming.json
```

Use `--storage` for a non-default Screenpipe folder. CPU reports 100% per core; RAM is peak process RSS; storage reports real byte deltas. These samples do not measure FPS, GPU load, or guarantee a representative day. Measure at least one day of recording before extrapolating storage. The harness never starts a game, enables recording, or saves personal screen/audio content.

On this machine Screenpipe is absent from port 3030. Therefore real Screenpipe capture, long-term retrieval, retention cleanup, and normal/gaming overhead are **not verified**. A baseline of the already running standalone companion is kept locally outside this repository, explicitly not a benchmark of this new fork integration. No gaming benchmark has been fabricated.

## Licence review (13 October 2026)

The current upstream `LICENSE.md` is the Screenpipe Commercial License, not MIT. It permits personal/non-commercial use and restricts commercial use, embedding, customer distribution and competing products without a commercial licence. Official builds have separate terms. Older MIT releases retain their earlier terms. The adapter is original code using HTTP; the fork's original Clicky licence/attribution remains unchanged. This architecture is not a determination that commercial distribution is permitted: resolve applicable licences with the licensor before shipping a commercial integration. No Screenpipe source was copied into this product.

Primary references:

- https://github.com/screenpipe/screenpipe/blob/main/LICENSE.md
- https://docs.screenpipe.com/api-reference/search/search-screen-and-audio-content
- https://docs.screenpipe.com/api-reference/frames/get-frame-by-id
- https://docs.screenpipe.com/api-reference/data-retention/configure-retention-policy
- https://github.com/screenpipe/screenpipe/blob/main/crates/screenpipe-core/assets/skills/screenpipe-api/SKILL.md
