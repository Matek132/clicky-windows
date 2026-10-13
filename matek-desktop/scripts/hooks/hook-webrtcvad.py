"""The Windows wheel distribution is webrtcvad-wheels, not webrtcvad."""
from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("webrtcvad-wheels")
hiddenimports = ["_webrtcvad"]
