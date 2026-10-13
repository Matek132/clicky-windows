@echo off
setlocal
cd /d "%~dp0.."
rem Keep unrelated tool runtimes out of native DLL discovery (notably ICU).
set "PATH=%CD%\.venv\Scripts;%SystemRoot%\System32;%SystemRoot%"
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name MatekScreenCompanion --exclude-module PyQt6 --additional-hooks-dir scripts\hooks --add-data "config\pricing.json;config" --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers --collect-all av --hidden-import keyring.backends.Windows --hidden-import webrtcvad --copy-metadata PySide6 --copy-metadata mss --copy-metadata faster-whisper --copy-metadata PyAudioWPatch --copy-metadata webrtcvad-wheels --copy-metadata httpx --copy-metadata keyring main.py
if errorlevel 1 exit /b 1
if exist "models\whisper-tiny.en\model.bin" (
  robocopy "models\whisper-tiny.en" "dist\MatekScreenCompanion\models\whisper-tiny.en" /E /NFL /NDL /NJH /NJS
  if errorlevel 8 exit /b 1
)
echo Built dist\MatekScreenCompanion\MatekScreenCompanion.exe
if exist "knowledge" (
  robocopy "knowledge" "dist\MatekScreenCompanion\knowledge" /E /NFL /NDL /NJH /NJS
  if errorlevel 8 exit /b 1
)
if exist "assets\matek.ico" copy /Y "assets\matek.ico" "dist\MatekScreenCompanion\matek.ico" >nul
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File scripts\verify_package.ps1
if errorlevel 1 exit /b 1
