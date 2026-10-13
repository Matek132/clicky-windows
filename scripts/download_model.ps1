$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe' }
& $pythonPath -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-base', local_dir='models/whisper-base', allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.txt','vocabulary.json'])"
if ($LASTEXITCODE -ne 0) { throw 'Offline speech model download failed.' }
