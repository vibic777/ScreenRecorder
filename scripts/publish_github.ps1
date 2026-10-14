# Publish ScreenRec sources and Windows release assets to GitHub.
# Requires: gh auth login, git remote origin pointing at your GitHub repo.
param(
    [string]$Version = "",
    [string]$Repo = "",
    [switch]$CreateRepo,
    [ValidateSet("public", "private")]
    [string]$Visibility = "public",
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required. Install: winget install --id GitHub.cli"
}

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Not logged in to GitHub. Run: gh auth login --web"
}

if (-not $Version) {
    $toml = Get-Content (Join-Path $Root "pyproject.toml") -Raw
    if ($toml -match 'version\s*=\s*"([^"]+)"') {
        $Version = $Matches[1]
    } else {
        throw "Cannot read version from pyproject.toml"
    }
}

$ReleaseDir = Join-Path (Join-Path $Root "releases") $Version
if (-not (Test-Path $ReleaseDir)) {
    throw "Local release folder missing: $ReleaseDir. Run scripts\release_windows.bat first."
}

$Required = @(
    "ScreenRec-$Version-Windows10-11-x64.exe",
    "ScreenRec-$Version-Windows10-11-x64.zip",
    "ScreenRec-$Version-Windows8-8.1-x64.exe",
    "ScreenRec-$Version-Windows8-8.1-x64.zip",
    "ScreenRec-$Version-source.zip",
    "ScreenRec-$Version-browser-extension.zip",
    "SHA256SUMS.txt",
    "manifest.json",
    "CHANGELOG.md"
)
foreach ($name in $Required) {
    $path = Join-Path $ReleaseDir $name
    if (-not (Test-Path $path)) {
        throw "Missing release artifact: $path"
    }
}

$manifestPath = Join-Path $ReleaseDir "manifest.json"
$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$head = git -c "safe.directory=$($Root -replace '\\','/')" rev-parse HEAD
if ($manifest.version -ne $Version -or $manifest.commit -ne $head) {
    throw "Release manifest does not match version $Version and current commit $head. Rebuild the release first."
}

$contributors = @(git -c "safe.directory=$($Root -replace '\\','/')" log --all --format='%an <%ae>' | Sort-Object -Unique)
$expectedContributor = "vibic777 <vibic777@users.noreply.github.com>"
if ($contributors.Count -ne 1 -or $contributors[0] -cne $expectedContributor) {
    throw "Expected only contributor $expectedContributor; found: $($contributors -join ', ')"
}

foreach ($line in Get-Content (Join-Path $ReleaseDir "SHA256SUMS.txt") -Encoding UTF8) {
    if ($line -notmatch '^(?<hash>[0-9a-fA-F]{64})  (?<name>.+)$') {
        throw "Invalid SHA256SUMS entry: $line"
    }
    $assetPath = Join-Path $ReleaseDir $Matches.name
    if (-not (Test-Path $assetPath -PathType Leaf)) {
        throw "Checksum target missing: $assetPath"
    }
    $actualHash = (Get-FileHash $assetPath -Algorithm SHA256).Hash
    if ($actualHash -ine $Matches.hash) {
        throw "Checksum mismatch: $assetPath"
    }
}

$status = git -c "safe.directory=$($Root -replace '\\','/')" status --porcelain
if ($status) {
    throw "Working tree is dirty. Commit or stash before publishing."
}

$Tag = "v$Version"
$existingTag = git -c "safe.directory=$($Root -replace '\\','/')" tag -l $Tag
if (-not $existingTag) {
    git -c "safe.directory=$($Root -replace '\\','/')" tag -a $Tag -m "ScreenRec $Version"
    if ($LASTEXITCODE -ne 0) { throw "Could not create annotated tag $Tag" }
} else {
    $tagCommit = git -c "safe.directory=$($Root -replace '\\','/')" rev-parse "$Tag^{commit}"
    if ($tagCommit -ne $head) {
        throw "Tag $Tag points to $tagCommit instead of current commit $head"
    }
}

$remote = git -c "safe.directory=$($Root -replace '\\','/')" remote get-url origin 2>$null
if (-not $remote) {
    if (-not $Repo) {
        throw "No git remote 'origin'. Pass -Repo owner/name (and optionally -CreateRepo)."
    }
    if ($CreateRepo) {
        gh repo create $Repo --$Visibility --source=. --remote=origin --description "ScreenRec - desktop screen recorder"
    } else {
        git remote add origin "https://github.com/$Repo.git"
    }
} elseif ($Repo) {
    Write-Host "Using existing origin remote; -Repo ignored: $remote"
}

if (-not $SkipPush) {
    git -c "safe.directory=$($Root -replace '\\','/')" push -u origin HEAD
    git -c "safe.directory=$($Root -replace '\\','/')" push origin $Tag
}

$notesFile = Join-Path $env:TEMP "screenrec-release-$Version.md"
$changelog = Get-Content (Join-Path $ReleaseDir "CHANGELOG.md") -Raw -Encoding UTF8
$releasePattern = '(?ms)^## ' + [regex]::Escape($Version) + '[^\r\n]*\r?\n(.*?)(?=^## |\z)'
$section = if ($changelog -match $releasePattern) {
    $Matches[1].Trim()
} else {
    "ScreenRec $Version"
}
@(
    "## ScreenRec $Version"
    ""
    $section
    ""
    "### Windows assets"
    "- ``ScreenRec-$Version-Windows10-11-x64.exe`` and ZIP - Windows 10/11 x64"
    "- ``ScreenRec-$Version-Windows8-8.1-x64.exe`` and ZIP - Windows 8/8.1 x64"
    "- ``ScreenRec-$Version-source.zip`` - source archive for this tag"
    "- ``ScreenRec-$Version-browser-extension.zip`` - Chrome/Edge extension"
    "- ``SHA256SUMS.txt`` / ``manifest.json`` - checksums and build metadata"
    ""
    "### Capture test note"
    "The Windows 10/11 region self-test was skipped because the build session denied BitBlt desktop capture. The Windows 8/8.1 region self-test passed."
) | Set-Content -Path $notesFile -Encoding UTF8

$assets = @(
    (Join-Path $ReleaseDir "ScreenRec-$Version-Windows10-11-x64.exe"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-Windows10-11-x64.zip"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-Windows8-8.1-x64.exe"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-Windows8-8.1-x64.zip"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-source.zip"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-browser-extension.zip"),
    (Join-Path $ReleaseDir "SHA256SUMS.txt"),
    (Join-Path $ReleaseDir "manifest.json")
)

$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $null = gh release view $Tag 2>&1
    $releaseViewExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorAction
}
if ($releaseViewExitCode -eq 0) {
    Write-Host "Release $Tag already exists; uploading/replacing assets..."
    gh release upload $Tag @assets --clobber
} else {
    gh release create $Tag @assets --title "ScreenRec $Version" --notes-file $notesFile
}

Write-Host "Published $Tag"
gh release view $Tag
gh repo view --json url -q .url
