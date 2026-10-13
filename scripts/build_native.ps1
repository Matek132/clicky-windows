$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create a Python 3.11 virtual environment and install requirements.txt first.' }
$env:PATH = "$(Split-Path $pythonPath);$env:SystemRoot\System32;$env:SystemRoot"
& $pythonPath -m PyInstaller clicky.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
$modelPath = Join-Path $projectRoot 'models\whisper-base'
if (-not (Test-Path -LiteralPath $modelPath)) { throw 'Download the offline speech model with scripts/download_model.ps1 first.' }
New-Item -ItemType Directory -Force 'dist\MatekScreenCompanion\models' | Out-Null
Copy-Item -LiteralPath $modelPath -Destination 'dist\MatekScreenCompanion\models' -Recurse -Force
Copy-Item -LiteralPath 'docs\THIRD_PARTY.md' -Destination 'dist\MatekScreenCompanion\THIRD_PARTY.md' -Force
& $pythonPath scripts\license_inventory.py 'dist\MatekScreenCompanion\licenses'
Write-Output 'Built dist/MatekScreenCompanion/MatekScreenCompanion.exe. Distribute the entire folder.'
