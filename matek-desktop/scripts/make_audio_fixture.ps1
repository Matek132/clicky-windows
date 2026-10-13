$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$fixtureDirectory = Join-Path $PSScriptRoot '..\tests\fixtures'
New-Item -ItemType Directory -Path $fixtureDirectory -Force | Out-Null
$fixturePath = [System.IO.Path]::GetFullPath((Join-Path $fixtureDirectory 'question.wav'))
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$speaker.SetOutputToWaveFile($fixturePath, $format)
$speaker.Speak('What does this symbol mean?')
$speaker.Dispose()
Write-Output "Generated local test speech: $fixturePath"
