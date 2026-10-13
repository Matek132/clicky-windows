$ErrorActionPreference = 'Stop'
$projectDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$packageExecutable = Join-Path $projectDirectory 'dist\MatekScreenCompanion\MatekScreenCompanion.exe'
$artifactsDirectory = Join-Path $projectDirectory 'artifacts'
New-Item -ItemType Directory -Path $artifactsDirectory -Force | Out-Null

function Invoke-PackageCheck([string[]] $CheckArguments, [int] $TimeoutMs) {
    $checkProcess = Start-Process -FilePath $packageExecutable -ArgumentList $CheckArguments -WindowStyle Hidden -PassThru
    if (-not $checkProcess.WaitForExit($TimeoutMs)) {
        Stop-Process -Id $checkProcess.Id
        throw 'Packaged application verification timed out'
    }
    if ($checkProcess.ExitCode -ne 0) {
        throw "Packaged application returned exit code $($checkProcess.ExitCode); inspect output JSON"
    }
}

$smokeReport = Join-Path $artifactsDirectory 'packaged-smoke.json'
if (Test-Path -LiteralPath $smokeReport) { Remove-Item -LiteralPath $smokeReport }
Invoke-PackageCheck -CheckArguments @('--smoke-test', '--output', ('"' + $smokeReport + '"')) -TimeoutMs 30000
$smoke = Get-Content -LiteralPath $smokeReport -Raw | ConvertFrom-Json
if ($smoke.smoke_exit -ne 0) { throw 'Smoke report did not confirm success' }
Write-Output 'Packaged native UI startup/shutdown: passed'

$voiceReport = Join-Path $artifactsDirectory 'packaged-voice.json'
if (Test-Path -LiteralPath $voiceReport) { Remove-Item -LiteralPath $voiceReport }
Invoke-PackageCheck -CheckArguments @('--speech-test', '--output', ('"' + $voiceReport + '"')) -TimeoutMs 25000
$voice = Get-Content -LiteralPath $voiceReport -Raw | ConvertFrom-Json
if (-not $voice.success -or $voice.caption_updates -lt 5 -or $voice.cloud_requests -ne 0) {
    throw 'Packaged offline voice/caption check failed'
}
Write-Output "Packaged offline voice/captions: $($voice.voice)"

$fixture = Join-Path $projectDirectory 'tests\fixtures\question.wav'
$packagedModel = Join-Path $projectDirectory 'dist\MatekScreenCompanion\models\whisper-tiny.en\model.bin'
if ((Test-Path -LiteralPath $fixture) -and (Test-Path -LiteralPath $packagedModel)) {
    $speechReport = Join-Path $artifactsDirectory 'packaged-transcription.json'
    if (Test-Path -LiteralPath $speechReport) { Remove-Item -LiteralPath $speechReport }
    $env:HF_HUB_OFFLINE = '1'
    Invoke-PackageCheck -CheckArguments @('--transcribe-file', ('"' + $fixture + '"'), '--output', ('"' + $speechReport + '"')) -TimeoutMs 45000
    $speech = Get-Content -LiteralPath $speechReport -Raw | ConvertFrom-Json
    if ($speech.text -notmatch '(?i)what.*mean' -or $speech.cloud_requests -ne 0) { throw 'Packaged offline speech check failed' }
    Write-Output "Packaged offline transcription: $($speech.text)"
} else {
    Write-Output 'Packaged transcription check skipped: model or generated fixture absent'
}
