param(
    [string]$Version = "1.0.0",
    [string]$RepoRoot
)

$ErrorActionPreference = "Stop"

$repoRoot = if ($RepoRoot) {
    (Resolve-Path $RepoRoot).Path
} else {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
$workRoot = Join-Path $PSScriptRoot "work"
$payload = Join-Path $workRoot "payload"
$outDir = Join-Path $PSScriptRoot "out"
$issFile = Join-Path $PSScriptRoot "RoadGISPro.iss"

if (-not (Test-Path $issFile)) {
    throw "Inno script not found: $issFile"
}

Write-Host "Preparing payload..."
& (Join-Path $PSScriptRoot "prepare_payload.ps1") -RepoRoot $repoRoot

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir | Out-Null
}

$isccCandidates = @(
    $env:ISCC_PATH,
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }
$isccCandidates = @($isccCandidates)

if ($isccCandidates.Count -eq 0) {
    throw "ISCC.exe not found. Install Inno Setup 6 or set ISCC_PATH."
}

$iscc = $isccCandidates[0]
Write-Host "Compiling installer with $iscc ..."
& $iscc `
    "/DMyAppVersion=$Version" `
    "/DSourceDir=$payload" `
    "/DOutputDir=$outDir" `
    $issFile

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
}

Write-Host "Done. Installer output is in: $outDir"
