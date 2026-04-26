from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import traceback
from typing import Any


def ursina_available() -> bool:
    return importlib.util.find_spec("ursina") is not None


def launch_ursina_view(scene_payload: dict[str, Any], log_path: str) -> tuple[bool, str]:
    if not ursina_available():
        return False, "Ursina is not installed in this Python environment."
    fd, scene_path = tempfile.mkstemp(prefix="roadgis_ursina_", suffix=".json")
    os.close(fd)
    with open(scene_path, "w", encoding="utf-8") as handle:
        json.dump(scene_payload, handle)
    cmd = [sys.executable, os.path.abspath(__file__), scene_path, log_path]
    try:
        subprocess.Popen(cmd)
    except OSError as ex:
        return False, f"Failed to launch Ursina view: {ex}"
    return True, "Opened Ursina 3D view in a separate window."


def _terrain_color(wx: float, wy: float) -> tuple[int, int, int]:
    seed = int(wx // 160.0) * 1619 + int(wy // 160.0) * 31337
    seed ^= seed >> 9
    blend = (seed & 255) / 255.0
    if blend < 0.2:
        a, b = (125, 132, 118), (160, 166, 152)
    elif blend < 0.4:
        a, b = (148, 136, 90), (186, 170, 112)
    elif blend < 0.72:
        a, b = (62, 118, 68), (104, 165, 96)
    else:
        a, b = (118, 154, 74), (176, 194, 112)
    return tuple(int(a[i] + (b[i] - a[i]) * blend) for i in range(3))


def _road_color(surface: str, texture_mode: str) -> tuple[int, int, int]:
    mode = texture_mode if texture_mode != "surface" else surface
    if mode == "concrete":
        return (142, 146, 144)
    if mode in ("gravel", "cobblestone"):
        return (147, 130, 105)
    if mode == "dirt":
        return (137, 92, 56)
    return (58, 60, 64)


def _run_ursina(scene_path: str, log_path: str) -> None:
    from ursina import AmbientLight, DirectionalLight, EditorCamera, Entity, Sky, Text, Ursina, Vec3, color, time, window

    with open(scene_path, "r", encoding="utf-8") as handle:
        scene = json.load(handle)

    roads = scene.get("roads", [])
    structures = scene.get("structures", [])
    texture_mode = str(scene.get("texture_mode", "surface"))
    show_trees = bool(scene.get("show_trees", True))
    show_lights = bool(scene.get("show_streetlights", True))
    route_path = scene.get("route_path", [])

    app = Ursina(borderless=False, title="RoadGIS Pro 3D View")
    window.color = color.rgb(135, 189, 226)
    Sky()
    sun = DirectionalLight()
    sun.look_at(Vec3(1, -1, -1))
    AmbientLight(color=color.rgba(170, 180, 195, 0.7))
    camera = EditorCamera(rotation_speed=120, panning_speed=160, zoom_speed=1.8)
    camera.position = (0, 180, -120)
    camera.rotation_x = 48

    hud = Text(
        text="RoadGISPro 3D | Right mouse orbit | Middle mouse pan | Wheel zoom | F fog | R rain | N day/night",
        origin=(-0.5, 0),
        x=-0.48,
        y=0.46,
        scale=1.0,
        color=color.white,
    )
    _ = hud

    day_night_enabled = {"value": True}
    fog_enabled = {"value": False}
    rain_enabled = {"value": False}
    rain_entities: list[Entity] = []

    xs: list[float] = []
    ys: list[float] = []
    for road in roads:
        for pt in road.get("geom", []):
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
    for st in structures:
        for pt in st.get("footprint", []):
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
    if not xs:
        xs = [0.0, 800.0]
        ys = [0.0, 800.0]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    tile_step = max(120.0, max(maxx - minx, maxy - miny, 400.0) / 8.0)
    tx = minx - tile_step
    while tx <= maxx + tile_step:
        ty = miny - tile_step
        while ty <= maxy + tile_step:
            r, g, b = _terrain_color(tx, ty)
            Entity(
                model="cube",
                position=(tx, -1.25, ty),
                scale=(tile_step, 0.5, tile_step),
                color=color.rgb(r, g, b),
                collider=None,
            )
            ty += tile_step
        tx += tile_step

    for road in roads:
        geom = road.get("geom", [])
        lanes = max(1, int(float(road.get("lanes", 1) or 1)))
        level = max(0.0, float(road.get("bridge_level", 0) or 0.0)) * 1.8
        width = 4.2 + lanes * 1.4
        road_rgb = _road_color(str(road.get("surface", "asphalt")), texture_mode)
        road_color = color.rgb(*road_rgb)
        for idx in range(len(geom) - 1):
            a = geom[idx]
            b = geom[idx + 1]
            if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)):
                continue
            ax, ay = float(a[0]), float(a[1])
            bx, by = float(b[0]), float(b[1])
            dx = bx - ax
            dy = by - ay
            length = math.hypot(dx, dy)
            if length <= 0.01:
                continue
            midx = (ax + bx) * 0.5
            midy = (ay + by) * 0.5
            heading = math.degrees(math.atan2(dy, dx))
            Entity(
                model="cube",
                position=(midx, level, midy),
                scale=(length, 0.5, width),
                rotation=(0, -heading, 0),
                color=road_color,
            )
            if show_lights and idx % 4 == 0 and level <= 0.01:
                nx = -dy / length
                ny = dx / length
                for sign in (-1, 1):
                    Entity(
                        model="cube",
                        position=(midx + nx * sign * (width * 0.65), 3.8, midy + ny * sign * (width * 0.65)),
                        scale=(0.35, 7.0, 0.35),
                        color=color.rgb(185, 188, 192),
                    )
                    Entity(
                        model="sphere",
                        position=(midx + nx * sign * (width * 0.65), 7.6, midy + ny * sign * (width * 0.65)),
                        scale=0.8,
                        color=color.rgba(255, 235, 180, 180),
                    )
            if show_trees and idx % 5 == 0 and level <= 0.01:
                nx = -dy / length
                ny = dx / length
                for sign in (-1, 1):
                    Entity(
                        model="cube",
                        position=(midx + nx * sign * (width * 1.25), 2.1, midy + ny * sign * (width * 1.25)),
                        scale=(0.55, 4.2, 0.55),
                        color=color.rgb(104, 74, 50),
                    )
                    Entity(
                        model="sphere",
                        position=(midx + nx * sign * (width * 1.25), 5.8, midy + ny * sign * (width * 1.25)),
                        scale=2.8,
                        color=color.rgb(72, 142, 76),
                    )

    for structure in structures:
        footprint = structure.get("footprint", [])
        if not isinstance(footprint, list) or len(footprint) < 3:
            continue
        pts = [(float(pt[0]), float(pt[1])) for pt in footprint if isinstance(pt, (list, tuple)) and len(pt) >= 2]
        if len(pts) < 3:
            continue
        cx = sum(pt[0] for pt in pts) / len(pts)
        cy = sum(pt[1] for pt in pts) / len(pts)
        width = max(8.0, min(28.0, math.sqrt(len(pts)) * 7.5))
        depth = max(8.0, min(28.0, width * 0.9))
        height = max(8.0, min(80.0, float(structure.get("height", 18.0))))
        Entity(
            model="cube",
            position=(cx, height * 0.5, cy),
            scale=(width, height, depth),
            color=color.rgb(88, 102, 116),
        )

    if len(route_path) > 1:
        for idx in range(len(route_path) - 1):
            a = route_path[idx]
            b = route_path[idx + 1]
            ax, ay = float(a[0]), float(a[1])
            bx, by = float(b[0]), float(b[1])
            dx = bx - ax
            dy = by - ay
            length = math.hypot(dx, dy)
            if length <= 0.01:
                continue
            midx = (ax + bx) * 0.5
            midy = (ay + by) * 0.5
            heading = math.degrees(math.atan2(dy, dx))
            Entity(
                model="cube",
                position=(midx, 1.2, midy),
                scale=(length, 0.2, 1.3),
                rotation=(0, -heading, 0),
                color=color.rgb(232, 70, 58),
            )

    def _toggle_rain() -> None:
        rain_enabled["value"] = not rain_enabled["value"]
        if rain_enabled["value"] and not rain_entities:
            for offset in range(80):
                rain_entities.append(
                    Entity(
                        model="cube",
                        scale=(0.08, 2.4, 0.08),
                        position=(minx + (offset % 10) * 30, 40 + (offset // 10) * 6, miny + (offset % 8) * 34),
                        color=color.rgba(190, 220, 255, 120),
                    )
                )
        for entity in rain_entities:
            entity.enabled = rain_enabled["value"]

    def input(key: str) -> None:
        if key == "n":
            day_night_enabled["value"] = not day_night_enabled["value"]
        elif key == "f":
            fog_enabled["value"] = not fog_enabled["value"]
        elif key == "r":
            _toggle_rain()
        elif key == "escape":
            from ursina import application
            application.quit()

    def update() -> None:
        cycle = (math.sin(time.time() * 0.1) + 1.0) * 0.5 if day_night_enabled["value"] else 0.8
        sky_red = int(65 + cycle * 95)
        sky_green = int(88 + cycle * 110)
        sky_blue = int(110 + cycle * 115)
        if fog_enabled["value"]:
            sky_red = int((sky_red + 175) * 0.5)
            sky_green = int((sky_green + 182) * 0.5)
            sky_blue = int((sky_blue + 188) * 0.5)
        window.color = color.rgb(sky_red, sky_green, sky_blue)
        sun.rotation = Vec3(35 + cycle * 45, -60 + cycle * 90, 0)
        if rain_enabled["value"]:
            for index, entity in enumerate(rain_entities):
                entity.y -= 18 * time.dt
                if entity.y < 2:
                    entity.y = 48 + (index % 7) * 3

    app.run()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return 1
    scene_path = argv[1]
    log_path = argv[2] if len(argv) > 2 else ""
    try:
        _run_ursina(scene_path, log_path)
        return 0
    except Exception:
        if log_path:
            try:
                with open(log_path, "a", encoding="utf-8") as handle:
                    handle.write("\n[Ursina view failure]\n")
                    handle.write(traceback.format_exc())
                    handle.write("\n")
            except OSError:
                pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
