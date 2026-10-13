# Optional Screenpipe memory

Matek's actual Clicky-based orchestrator continues to own questions, reasoning, spoken answers and its interface. Screenpipe is a separate optional local history service; no Screenpipe source or recorder binary is bundled. It is currently absent from localhost:3030 on this PC.

## Configuration

Keep Settings → Privacy / memory → memory backend set to `ram` for a fully independent companion. To use a separately installed Screenpipe, select `screenpipe`, leave its API on loopback `http://127.0.0.1:3030`, and enter its local token in the Windows-vault field. Configure `SCREENPIPE_LOCAL_API_KEY` in that service. The adapter uses Bearer authentication, disables proxy inheritance and redirects, and does not contact a paid AI service. Do not expose the port to the LAN. Missing/unavailable service or token falls back to RAM.

Configure Screenpipe to record the permitted screen and system output, while leaving microphone capture to Matek. The native adapter checks recorder health every five seconds and uses fresh source timestamps before suspending its own continuous capture of that source. A transition can overlap until the next health check; there is no cross-process lease. A current pointing request can still take one explicit fresh screenshot, because historical pixels cannot supply current pointer coordinates.

Screenpipe's own recorder privacy filters must exclude password managers, private browsers, banking, credentials and other sensitive windows. Matek's filters additionally restrict retrieval before selected frame downloads. They cannot undo an independent recorder's previous capture. Pausing Matek does not stop Screenpipe or delete its files. Review recorder encryption/redaction controls and local storage access separately.

Queries are clamped to the saved retention-day limit. Physical retention is configured only by the explicit retention button after settings are saved and the service accepts it; the independent service performs deletion. No direct SQLite access or server-supplied file paths are used.

## Context selection

The documented local API supplies bounded search/OCR/application/audio history and selected frames. Search requests set `include_cloud=false` and `include_frames=false`; relevant frame IDs are fetched separately. At most 30 metadata rows, eight selected excerpts and three downscaled images enter a request. Responses are bounded to 8 MiB and requests to three seconds each. Seconds/minutes/hours/days, “ago”, today/yesterday/last week are supported; unsupported time phrasing falls back to two minutes.

Without Screenpipe, Matek's own RAM backend retains at most 120 seconds, 24 frames by default, a configurable image-byte ceiling, and 100 transcript entries. Its local WASAPI loopback works independently of Screenpipe. General-knowledge questions work with both memory backends disabled. Captured content is evidence, never an instruction; uncaptured events remain unknown.

## Evidence and limits

Adapter authentication, bounds, filtering, frame formats, fallback and capture ownership have automated local API fixture tests. Actual Screenpipe recording, long-term retrieval, retention cleanup, daily storage and normal/game overhead are not verified because the service is not installed. See [native companion measurements](VALIDATION.md) for separate results; they must not be presented as Screenpipe measurements. `scripts/benchmark_memory.py` can sample actual Screenpipe/companion processes and storage when a recorder is available; its operator-supplied gaming label does not prove a game is running.

## Licence review — 13 October 2026

The [current upstream licence](https://github.com/screenpipe/screenpipe/blob/main/LICENSE.md) is Commercial License. Personal/noncommercial terms differ from commercial embedding, distribution and competing-product use; official builds have separate terms. Obtain the relevant review/permission before offering a commercial integration. Older MIT releases retain their earlier terms. HTTP separation alone does not establish commercial permission.

Primary API references: [search](https://docs.screenpipe.com/api-reference/search/search-screen-and-audio-content), [frames](https://docs.screenpipe.com/api-reference/frames/get-frame-by-id), [retention](https://docs.screenpipe.com/api-reference/data-retention/configure-retention-policy).
