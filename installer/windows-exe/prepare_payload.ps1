param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$workRoot = Join-Path $PSScriptRoot "work"
$pyiBuild = Join-Path $workRoot "pyi-build"
$pyiDist = Join-Path $workRoot "pyi-dist"
$payload = Join-Path $workRoot "payload"
$components = Join-Path $payload "components"
$coreDir = Join-Path $components "core"

if (Test-Path $workRoot) {
    Remove-Item -Recurse -Force $workRoot
}
New-Item -ItemType Directory -Path $workRoot, $pyiBuild, $pyiDist, $payload, $components, $coreDir | Out-Null

$appEntry = Join-Path $RepoRoot "RoadGISPro.py"
if (-not (Test-Path $appEntry)) {
    throw "RoadGISPro.py not found at $appEntry"
}

Write-Host "[1/4] Building RoadGISPro executable with PyInstaller..."
Push-Location $RepoRoot
try {
    function Resolve-PythonExe {
        if ($PythonExe) {
            return $PythonExe
        }
        $py = Get-Command python -ErrorAction SilentlyContinue
        if ($py) {
            return $py.Source
        }
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            return "py"
        }
        throw "Python not found. Install Python 3.x or pass -PythonExe."
    }

    $python = Resolve-PythonExe
    $pyinstallerOk = $true
    try {
        & $python -m PyInstaller --version | Out-Null
    } catch {
        $pyinstallerOk = $false
    }
    if (-not $pyinstallerOk) {
        Write-Host "PyInstaller not found. Installing..."
        & $python -m pip install pyinstaller
    }

    & $python -c "import tkinter" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Tkinter is not available in this Python. Install Python with Tcl/Tk support and retry."
    }

    $pyBase = (& $python -c "import sys; print(sys.base_prefix)").Trim()
    $tclRoot = $null
    foreach ($cand in @((Join-Path $pyBase "tcl"), (Join-Path (Split-Path $python -Parent) "tcl"))) {
        if (-not $tclRoot -and (Test-Path $cand)) {
            $tclRoot = $cand
        }
    }
    $addDataArgs = @()
    if ($tclRoot) {
        $tclDir = Get-ChildItem -Directory -Path $tclRoot -Filter "tcl8.*" | Select-Object -First 1
        $tkDir = Get-ChildItem -Directory -Path $tclRoot -Filter "tk8.*" | Select-Object -First 1
        if ($tclDir -and $tkDir) {
            $env:TCL_LIBRARY = $tclDir.FullName
            $env:TK_LIBRARY = $tkDir.FullName
            $addDataArgs = @(
                "--add-data", "$($tclDir.FullName);tcl\$($tclDir.Name)",
                "--add-data", "$($tkDir.FullName);tcl\$($tkDir.Name)"
            )
            Write-Host "Bundling Tcl/Tk from $tclRoot"
        } else {
            Write-Host "WARNING: Tcl/Tk directories not found under $tclRoot; tkinter may be missing."
        }
    } else {
        Write-Host "WARNING: Tcl root not found; tkinter may be missing."
    }

    $pyArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name", "RoadGISPro",
        "--distpath", $pyiDist,
        "--workpath", $pyiBuild,
        "--specpath", $workRoot
    ) + $addDataArgs + @($appEntry)

    & $python @pyArgs
} finally {
    Pop-Location
}

$builtAppDir = Join-Path $pyiDist "RoadGISPro"
if (-not (Test-Path $builtAppDir)) {
    throw "PyInstaller output not found: $builtAppDir"
}

Write-Host "[2/4] Staging core files..."
Copy-Item -Recurse -Force (Join-Path $builtAppDir "*") $coreDir

$polyglotRoot = Join-Path $RepoRoot "polyglot"
$corePolyglot = Join-Path $coreDir "polyglot"
New-Item -ItemType Directory -Path $corePolyglot | Out-Null

foreach ($item in @("plugins", "setup", "README.md", "runtime_config.example.json")) {
    $src = Join-Path $polyglotRoot $item
    if (Test-Path $src) {
        Copy-Item -Recurse -Force $src $corePolyglot
    }
}

foreach ($rootFile in @("README.md", "LICENSE")) {
    $src = Join-Path $RepoRoot $rootFile
    if (Test-Path $src) {
        Copy-Item -Force $src $coreDir
    }
}

Write-Host "[3/4] Staging optional language bundles..."
$langMap = @{
    "go"        = @("go", "validators/go_validator", "plugins/go_network_health")
    "rust"      = @("rust_router", "validators/rust_validator", "plugins/rust_surface_audit")
    "js"        = @("js")
    "ruby"      = @("ruby")
    "java"      = @("java")
    "csharp"    = @("csharp")
}

foreach ($lang in $langMap.Keys) {
    $langDir = Join-Path $components $lang
    New-Item -ItemType Directory -Path $langDir | Out-Null
    $langPoly = Join-Path $langDir "polyglot"
    New-Item -ItemType Directory -Path $langPoly | Out-Null
    foreach ($rel in $langMap[$lang]) {
        $src = Join-Path $polyglotRoot $rel
        if (Test-Path $src) {
            if ($rel -eq "rust_router") {
                robocopy $src (Join-Path $langPoly $rel) /E /XD "target" "__pycache__" | Out-Null
            } else {
                Copy-Item -Recurse -Force $src (Join-Path $langPoly $rel)
            }
        }
    }
    # keep folder non-empty so Inno wildcard has at least one file
    Set-Content -Path (Join-Path $langDir ".placeholder") -Value "placeholder"
}

Write-Host "[4/4] Payload ready at: $payload"

