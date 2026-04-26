# Linux PyInstaller Build

Supported target:

- Debian 11+
- Ubuntu and other close Debian derivatives

Build steps:

```bash
python3 -m pip install .[dev,3d]
./installer/linux-pyinstaller/build_app.sh 1.0.0
```

Output:

- `installer/linux-pyinstaller/out/RoadGISPro`

Notes:

- Run builds on the oldest Debian-family release you want to support.
- Tkinter and Panda3D/Ursina libraries must be available in the build environment.

