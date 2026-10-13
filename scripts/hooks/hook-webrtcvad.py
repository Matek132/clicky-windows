"""Installed VAD distribution is webrtcvad-wheels on Windows."""
from PyInstaller.utils.hooks import copy_metadata
datas = copy_metadata("webrtcvad-wheels")
hiddenimports = ["_webrtcvad"]
