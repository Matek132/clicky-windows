# Third-party components and distribution review

The existing Clicky source licence and Shashank Singh attribution remain in `LICENSE`. Matek extends that source and uses PyQt6; the local executable is built for this user's personal machine. This document is not clearance for a proprietary or commercially distributed binary.

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt) is available under GPL v3 or a Riverbank commercial licence. Review the applicable PyQt/Qt terms and provide required notices/source when distributing binaries; the upstream MIT source licence does not replace dependency obligations.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [CTranslate2](https://github.com/OpenNMT/CTranslate2) provide offline recognition. The [converted multilingual base model](https://huggingface.co/Systran/faster-whisper-base) is identified as MIT by its publisher and derives from OpenAI Whisper. Preserve its applicable notices when distributing model files.
- Windows SAPI speech is provided by the operating system; installed Windows voices are not copied into the distribution.
- Ollama and its separately downloaded `qwen2.5vl:3b` model are separate installations. Their weights are not bundled in this executable folder; review the specific model's licence before redistributing weights.
- PortAudio/PyAudioWPatch, WebRTC VAD, Pillow, numpy, mss, HTTPX, keyring, psutil and other original Clicky provider/document/OCR packages have their own licences. The bundled Qt, OpenSSL, FFmpeg, ONNX and OpenCV native binaries also require their own notices. `scripts/build_native.ps1` creates an installed-package licence inventory alongside the binary.
- Screenpipe is a separate optional service. No Screenpipe source or binary is included. The [current Screenpipe Commercial License](https://github.com/screenpipe/screenpipe/blob/main/LICENSE.md) distinguishes personal use, official builds, and commercial integrations. Resolve commercial/embedding/distribution permission with its licensor before shipping an integration to customers.

No commercial licences were purchased or assumed. No cloud subscription is required for the installed local configuration.
