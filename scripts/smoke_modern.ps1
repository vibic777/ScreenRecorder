$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$exe = Join-Path $root 'dist\modern\ScreenRec.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Modern EXE not found: $exe" }
$output = Join-Path $root '.test-output\modern'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$report = Join-Path $output 'selftest-mp4-none.json'
$process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -ArgumentList '--self-test','--output',$output,'--audio','none','--format','mp4','--synthetic' -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0) { throw "Modern EXE self-test failed: $($process.ExitCode)" }
if (-not (Test-Path -LiteralPath $report)) { throw "Self-test report not found: $report" }
$result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if (-not $result.ok) { throw "Modern self-test report is not successful" }
Write-Output "Modern EXE smoke test passed: exit=$($process.ExitCode), report=$report"