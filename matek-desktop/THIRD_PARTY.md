# Third-party components

This project uses open-source dependencies. Preserve their license notices when redistributing the application. Package metadata and the PyInstaller `_internal` directory contain many upstream notices; an installer/release audit is still required for public redistribution.

- Python: https://www.python.org/psf/license/
- PySide6/Qt: https://doc.qt.io/qtforpython-6/licenses.html (LGPL/GPL/commercial alternatives; observe applicable terms)
- MSS: https://github.com/BoboTiG/python-mss
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- Whisper: https://github.com/openai/whisper
- CTranslate2: https://github.com/OpenNMT/CTranslate2
- PyAudioWPatch / PortAudio: https://github.com/s0d3s/PyAudioWPatch
- WebRTC VAD wheels: https://github.com/daanzu/py-webrtcvad-wheels
- Pillow: https://python-pillow.org/
- NumPy: https://numpy.org/
- HTTPX: https://www.python-httpx.org/
- keyring: https://github.com/jaraco/keyring
- pytesseract / Tesseract: https://github.com/madmaze/pytesseract and https://github.com/tesseract-ocr/tesseract
- Ollama (optional separate runtime): https://github.com/ollama/ollama
- PyInstaller: https://pyinstaller.org/

The OpenAI API is an optional metered service, not a background dependency. No API key or paid subscription is bundled.
