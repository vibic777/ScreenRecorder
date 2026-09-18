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
    "ScreenRec.exe",
    "ScreenRec-$Version-windows-x64.zip",
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

$status = git -c "safe.directory=$($Root -replace '\\','/')" status --porcelain
if ($status) {
    throw "Working tree is dirty. Commit or stash before publishing."
}

$Tag = "v$Version"
$existingTag = git -c "safe.directory=$($Root -replace '\\','/')" tag -l $Tag
if (-not $existingTag) {
    throw "Annotated tag $Tag not found. Create it locally before publishing."
}

$remote = git -c "safe.directory=$($Root -replace '\\','/')" remote get-url origin 2>$null
if (-not $remote) {
    if (-not $Repo) {
        throw "No git remote 'origin'. Pass -Repo owner/name (and optionally -CreateRepo)."
    }
    if ($CreateRepo) {
        gh repo create $Repo --$Visibility --source=. --remote=origin --description "ScreenRec — desktop screen recorder"
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
$section = if ($changelog -match "(?ms)^## $([regex]::Escape($Version))[^\r\n]*\r?\n(.*?)(?=^## |\z)") {
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
    "- ``ScreenRec.exe`` — one-file Windows x64 build"
    "- ``ScreenRec-$Version-windows-x64.zip`` — EXE + docs + browser extension folder"
    "- ``ScreenRec-$Version-source.zip`` — source archive for this tag"
    "- ``ScreenRec-$Version-browser-extension.zip`` — Chrome/Edge extension"
    "- ``SHA256SUMS.txt`` / ``manifest.json`` — checksums and build metadata"
) | Set-Content -Path $notesFile -Encoding UTF8

$assets = @(
    (Join-Path $ReleaseDir "ScreenRec.exe"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-windows-x64.zip"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-source.zip"),
    (Join-Path $ReleaseDir "ScreenRec-$Version-browser-extension.zip"),
    (Join-Path $ReleaseDir "SHA256SUMS.txt"),
    (Join-Path $ReleaseDir "manifest.json")
)

$existingRelease = gh release view $Tag 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Release $Tag already exists; uploading/replacing assets..."
    gh release upload $Tag @assets --clobber
} else {
    gh release create $Tag @assets --title "ScreenRec $Version" --notes-file $notesFile
}

Write-Host "Published $Tag"
gh release view $Tag
gh repo view --json url -q .url
