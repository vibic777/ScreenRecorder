param([switch]$WhatIf)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targets = @('build', 'dist\modern', 'dist\legacy', 'dist-build') | ForEach-Object { Join-Path $root $_ }
foreach ($target in $targets) {
    $resolved = [IO.Path]::GetFullPath($target)
    if ($resolved -notlike "$root\*") { throw "Unsafe cleanup target: $resolved" }
    if (Test-Path -LiteralPath $resolved) {
        if ($WhatIf) { Write-Output "Would remove: $resolved" }
        else { Remove-Item -LiteralPath $resolved -Recurse -Force; Write-Output "Removed: $resolved" }
    }
}