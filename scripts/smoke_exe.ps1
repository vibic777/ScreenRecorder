param(
    [ValidateSet('none', 'microphone', 'system', 'both')][string]$Audio = 'none',
    [ValidateSet('mp4', 'mkv', 'webm')][string]$Format = 'mp4',
    [switch]$Synthetic
)
$ErrorActionPreference = 'Stop'
$screenrecRoot = Split-Path -Parent $PSScriptRoot
$screenrecFolder = Join-Path $screenrecRoot '.test-output\standalone'
New-Item -ItemType Directory -Force -Path $screenrecFolder | Out-Null
$screenrecExecutable = Join-Path $screenrecFolder 'ScreenRec.exe'
Copy-Item -LiteralPath (Join-Path $screenrecRoot 'dist\ScreenRec.exe') -Destination $screenrecExecutable
$env:PYTHONPATH = ''
$env:IMAGEIO_FFMPEG_EXE = ''
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$screenrecArguments = "--self-test --output results --audio $Audio --format $Format"
if ($Synthetic) { $screenrecArguments += ' --synthetic' }
$screenrecProcess = Start-Process -FilePath $screenrecExecutable -WorkingDirectory $screenrecFolder -ArgumentList $screenrecArguments -WindowStyle Hidden -PassThru -Wait
$screenrecReport = Join-Path $screenrecFolder "results\selftest-$Format-$Audio.json"
if (Test-Path -LiteralPath $screenrecReport) {
    $screenrecResult = Get-Content -LiteralPath $screenrecReport -Raw | ConvertFrom-Json
    $screenrecResult | Select-Object ok,file,frames,seconds,audio,ffmpeg,error | Format-List
}
if ($screenrecProcess.ExitCode -ne 0) { throw "EXE self-test failed: $($screenrecProcess.ExitCode)" }
