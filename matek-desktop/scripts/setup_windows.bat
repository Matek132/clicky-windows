@echo off
cd /d "%~dp0.."
py -m pip install uv
if errorlevel 1 exit /b 1
py -m uv venv --python 3.11.9 .venv
if errorlevel 1 exit /b 1
py -m uv pip install --python .venv\Scripts\python.exe -r requirements-lock.txt
if errorlevel 1 exit /b 1
echo Setup complete. Run scripts\download_model.bat for offline voice support.
pause
