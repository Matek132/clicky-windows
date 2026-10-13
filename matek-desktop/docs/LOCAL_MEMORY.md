# Installed local Matek memory

The desktop executable includes the optional Screenpipe API integration. Your existing mascot, hover typing/settings, always-ready microphone, silent ordinary replies, explicit “Matek…” spoken replies, offline Windows voice, Ollama and local reference notes remain available.

Hover over the mascot, open the gear and select **Memory**. The current installation uses **ram** and retains up to two minutes of recent screen/audio context in bounded RAM. No Screenpipe service, AI API key or GitHub connection is needed for this mode.

To connect a separately installed local Screenpipe recorder, select **screenpipe**, enter its loopback URL and its API token. Matek saves that token in the Windows credential vault; settings JSON contains no token. Keep the existing screen/system-audio permissions enabled only for sources you want retrieved. A fresh, healthy Screenpipe stream suppresses Matek's corresponding screen/system-audio capture. Matek always retains microphone question handling; configure Screenpipe to capture screen and system audio, with microphone recording disabled. Recorder ownership is polled every five seconds, so transitions can overlap briefly. Missing/stale service health re-enables built-in capture.

Maximum history days limits queries immediately. Save the settings, reopen them and press **Apply saved retention to Screenpipe** to configure its storage cleanup. That button changes the separate recorder's policy and can cause deletion of old recordings. Without successful API authentication and an accepted policy, no physical retention cleanup is configured by Matek.

Filters are applied to retrieved app/window/text metadata before fetching pixels. Also configure exclusions/redaction in Screenpipe itself; an adapter cannot undo persistent recording. Pausing/disabling Matek does not stop that independent recorder. Clear recent context clears Matek RAM, not Screenpipe files. General-knowledge questions omit captured history. Selected historical context is untrusted evidence, with bounded excerpts/images; no arbitrary database or server file paths are read.

Screenpipe is not installed/running on this machine at delivery. The API adapter was tested with deterministic fixtures, source ownership tests and unavailable-service fallback. Live Screenpipe retention, recording and gaming performance remain unverified. The installed RAM backend and offline speech/answer path were tested locally. Screenpipe source/binaries are not bundled, and its current licence requires review before commercial integration/distribution.
