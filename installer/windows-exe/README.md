# RoadGISPro Windows EXE Installer (Inno Setup)

This folder is a standalone installer pipeline, separate from app source folders.

It builds:

- a packaged app payload from `RoadGISPro.py`
- a wizard-style Windows installer `.exe`

## What this installer wizard supports

- choose install location
- optional desktop icon
- optional language tool bundles:
  - Go
  - Rust
  - JavaScript
  - Ruby
  - Java
  - C#

## Prerequisites (free)

- Python 3.x
- PyInstaller (`pip install pyinstaller`)
- Inno Setup 6 (`ISCC.exe`)

## Build the EXE installer

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\installer\windows-exe\build_exe.ps1" -Version "1.0.0"
```

If your repo is elsewhere:

```powershell
powershell -ExecutionPolicy Bypass -File ".\installer\windows-exe\build_exe.ps1" -Version "1.0.0" -RepoRoot "C:\path\to\RoadGISPro_fresh"
```

Note: run this from a normal (non-admin) PowerShell window. PyInstaller blocks admin/system32 builds.

Output:

- `installer/windows-exe/out/RoadGISProSetup-<version>.exe`

## Upload to GitHub Releases

After build, upload the generated `.exe` to your GitHub Release assets so users can download it next to source zip/tarball.

## Notes

- This does not generate MSI.
- MSI can be added separately with WiX Toolset when you are ready.

toodles bro