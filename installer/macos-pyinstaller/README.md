# macOS PyInstaller Build

Supported targets:

- macOS Sonoma
- macOS Sequoia
- macOS Tahoe
- Apple Silicon and Intel

Build steps:

```bash
python3 -m pip install .[dev,3d]
./installer/macos-pyinstaller/build_app.sh 1.0.0
```

Output:

- `installer/macos-pyinstaller/out/RoadGISPro.app`

Notes:

- Build on macOS with the matching Python architecture you want to ship.
- For universal builds, use a universal Python runtime before invoking PyInstaller.

