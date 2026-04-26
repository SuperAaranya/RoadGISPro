# RoadGISPro Packaging Matrix

RoadGISPro uses `PyInstaller` as the shared packaging baseline across desktop targets.

Targets included in this repo:

- `windows-exe/`: Windows 11 packaging with Inno Setup.
- `linux-pyinstaller/`: Debian 11+ and close derivatives.
- `macos-pyinstaller/`: macOS Sonoma, Sequoia, and Tahoe on Apple Silicon or Intel.

Recommended setup:

```powershell
python -m pip install .[dev,3d]
```

The optional `3d` extra installs Ursina so the separate 3D renderer can launch on all three desktop families.

