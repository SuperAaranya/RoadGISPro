# RoadGISPro

RoadGISPro is a desktop GIS tool for creating and editing road networks, then running fastest-time routing on those roads.

## Highlights

- Draw and edit road geometries with snapping.
- Store rich attributes per road:
  - road class/type
  - speed limit
  - lane count
  - one-way direction
  - tunnel / lighting flags
  - bridge level
  - max weight
  - surface type
- Fastest-time routing using your road attributes.
- Undo/redo, copy/paste, zoom fit, layer clearing.
- Save/load custom `.rgis` format and export/import JSON.

## Route Tool

1. Draw roads and commit them (right-click in Draw mode).
2. Switch to `Route` mode (`R` key or toolbar button).
3. Click a start point near a road vertex.
4. Click a destination point near a road vertex.
5. RoadGISPro computes and displays the fastest route, plus distance and ETA.
6. Right-click (or press `Esc`) in Route mode to clear the current route.

## Run

From the project folder:

```powershell
python RoadGISPro.py
```

## Windows Installer (EXE/MSI)

Installer build scripts live in:

`installer/windows-exe`

Quick build:

```powershell
powershell -ExecutionPolicy Bypass -File ".\installer\windows-exe\build_exe.ps1" -Version "1.0.0"
```

## Files

- `RoadGISPro.py`: Main application.
- `README.md`: Project overview.
- `CONTRIBUTING.md`: Contribution standards.
- `LICENSE`: MIT license.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening issues or pull requests.

## License

This project is licensed under the [MIT License](LICENSE).
