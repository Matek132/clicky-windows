# Configure this installation after Tesseract and Ollama have been installed.
$ErrorActionPreference = 'Stop'
$projectDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectDirectory
$ocrExecutable = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
$ollamaExecutable = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $ocrExecutable)) { throw 'Tesseract is not installed' }
if (-not (Test-Path -LiteralPath $ollamaExecutable)) { throw 'Ollama is not installed' }
& $ollamaExecutable pull qwen2.5vl:3b
if ($LASTEXITCODE -ne 0) { throw 'Local vision model download failed' }
& '.\.venv\Scripts\python.exe' -c "from companion.config import Settings; c=Settings.load(); c.mode='local'; c.local_model='qwen2.5vl:3b'; c.local_vision=True; c.tesseract_path=r'C:\Program Files\Tesseract-OCR\tesseract.exe'; c.cloud_access=False; c.activation='push'; c.system_questions=False; c.save(); print('Local vision answers configured; cloud transmission disabled')"
if ($LASTEXITCODE -ne 0) { throw 'Configuration failed' }
