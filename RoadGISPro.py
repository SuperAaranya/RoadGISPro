import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import uuid
import math
import os
import base64
import hashlib
import struct
import zlib
import copy
import heapq
import time
import shutil
import subprocess

FILE_MAGIC   = b"RGIS"
FILE_VERSION = 1
FILE_EXT     = ".rgis"
FILE_KEY     = b"RoadGISPro\x7f\x3a\x91\xb4\x2d\xe0\x55\xc8"
APP_TITLE    = "RoadGIS Pro"
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
POLYGLOT_DIR = os.path.join(BASE_DIR, "polyglot")
RUST_ROUTER_MANIFEST = os.path.join(POLYGLOT_DIR, "rust_router", "Cargo.toml")
RUST_ROUTER_BIN = os.path.join(
    POLYGLOT_DIR, "rust_router", "target", "release",
    "rust_router.exe" if os.name == "nt" else "rust_router",
)
JS_METRICS_SCRIPT = os.path.join(POLYGLOT_DIR, "js", "metrics.js")
GO_METRICS_SCRIPT = os.path.join(POLYGLOT_DIR, "go", "metrics.go")
CSHARP_METRICS_PROJECT = os.path.join(POLYGLOT_DIR, "csharp", "MetricsEngine.csproj")
PLUGIN_DIR = os.path.join(POLYGLOT_DIR, "plugins")
PLUGIN_REGISTRY_PATH = os.path.join(PLUGIN_DIR, "registry.json")
PLUGIN_MANIFESTS_DIR = os.path.join(PLUGIN_DIR, "manifests")
GO_VALIDATOR_SCRIPT = os.path.join(POLYGLOT_DIR, "validators", "go_validator", "validator.go")
RUST_VALIDATOR_MANIFEST = os.path.join(POLYGLOT_DIR, "validators", "rust_validator", "Cargo.toml")


def _derive_keystream(length: int) -> bytes:
    stream = bytearray()
    seed   = FILE_KEY
    while len(stream) < length:
        seed   = hashlib.sha256(seed).digest()
        stream += seed
    return bytes(stream[:length])


def encode_rgis(data) -> bytes:
    payload      = json.dumps(data, separators=(",", ":")).encode("utf-8")
    compressed   = zlib.compress(payload, level=9)
    keystream    = _derive_keystream(len(compressed))
    encrypted    = bytes(b ^ k for b, k in zip(compressed, keystream))
    checksum     = zlib.crc32(compressed) & 0xFFFFFFFF
    header       = FILE_MAGIC + struct.pack(">BII", FILE_VERSION, len(encrypted), checksum)
    encoded      = base64.b85encode(header + encrypted)
    return encoded


def decode_rgis(raw: bytes):
    try:
        blob = base64.b85decode(raw.strip())
    except Exception as ex:
        raise ValueError("Not a valid .rgis file (base85 decode failed).") from ex
    if len(blob) < 13:
        raise ValueError("File is too short to be a valid .rgis file.")
    magic = blob[:4]
    if magic != FILE_MAGIC:
        raise ValueError(f"Bad magic bytes - expected RGIS, got {magic!r}.")
    version, payload_len, checksum = struct.unpack(">BII", blob[4:13])
    if version != FILE_VERSION:
        raise ValueError(f"Unsupported file version {version}.")
    encrypted = blob[13:]
    if len(encrypted) != payload_len:
        raise ValueError("Payload length mismatch - file may be truncated or corrupt.")
    keystream = _derive_keystream(len(encrypted))
    compressed = bytes(b ^ k for b, k in zip(encrypted, keystream))
    if (zlib.crc32(compressed) & 0xFFFFFFFF) != checksum:
        raise ValueError("Checksum mismatch - file is corrupt or has been tampered with.")
    try:
        payload = zlib.decompress(compressed)
    except zlib.error as ex:
        raise ValueError("Compressed payload is invalid.") from ex
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as ex:
        raise ValueError("Decoded payload is not valid UTF-8 JSON.") from ex
    if isinstance(data, list):
        data = {"roads": data, "connectors": []}
    if not isinstance(data, dict) or "roads" not in data:
        raise ValueError("Decoded data is not a valid RoadGIS layer object.")
    if "connectors" not in data or not isinstance(data["connectors"], list):
        data["connectors"] = []
    return data


ROAD_STYLES = {
    "motorway":     {"color": "#e8463a", "casing": "#8a1a10", "width": 7,  "label": "Motorway"},
    "primary":      {"color": "#f5a623", "casing": "#7a4a00", "width": 5,  "label": "Primary"},
    "secondary":    {"color": "#f5e642", "casing": "#6a5e00", "width": 4,  "label": "Secondary"},
    "tertiary":     {"color": "#8ec44a", "casing": "#3a5200", "width": 3,  "label": "Tertiary"},
    "residential":  {"color": "#d8dde8", "casing": "#4a5068", "width": 2,  "label": "Residential"},
    "service":      {"color": "#b0b8d0", "casing": "#3a4058", "width": 1,  "label": "Service"},
    "unclassified": {"color": "#9098b0", "casing": "#303848", "width": 2,  "label": "Unclassified"},
}

ROAD_TYPES   = list(ROAD_STYLES.keys())
SURFACE_TYPES = ["asphalt", "concrete", "gravel", "dirt", "cobblestone", "paved"]

SNAP_PX      = 14
NODE_RADIUS  = 4
SMOOTH_STEPS = 16
ROUTE_PICK_PX = 48
CONNECT_PICK_PX = 20
CONNECTOR_TRAVEL_HOURS = 0.002
DRIVE_MAX_SPEED = 200.0
DRIVE_REVERSE_SPEED = 80.0
DRIVE_ACCEL = 210.0
DRIVE_BRAKE = 270.0
DRIVE_TURN_RATE = 2.4
DRIVE_LOCK_DIST = 90.0
DRIVE_HARD_LIMIT_DIST = 220.0

MAP_BG      = "#1a2030"
DARK_BG     = "#111520"
PANEL_BG    = "#111828"
PANEL_FG    = "#dde4f8"
ACCENT      = "#4a7ef5"
ACCENT2     = "#e8463a"
INPUT_BG    = "#0f1628"
INPUT_FG    = "#dde4f8"
BORDER      = "#1c2540"
SELECT_COL  = "#00e5ff"
HOVER_COL   = "#ffdd55"
GRID_COL    = "#1e2840"
GRID_LABEL  = "#2a3a60"


def catmull_rom_point(p0, p1, p2, p3, t):
    t2 = t * t
    t3 = t2 * t
    x = 0.5 * (
        (2 * p1[0])
        + (-p0[0] + p2[0]) * t
        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
    )
    y = 0.5 * (
        (2 * p1[1])
        + (-p0[1] + p2[1]) * t
        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
    )
    return (x, y)


def smooth_geom(geom):
    if len(geom) < 3:
        return geom
    pts  = geom
    ext  = [pts[0], *pts, pts[-1]]
    smoothed = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for step in range(SMOOTH_STEPS):
            smoothed.append(catmull_rom_point(p0, p1, p2, p3, step / SMOOTH_STEPS))
    smoothed.append(pts[-1])
    return smoothed


def label_positions(geom, min_spacing_world=150):
    if len(geom) < 2:
        return []
    segs  = []
    total = 0.0
    for i in range(len(geom) - 1):
        ax, ay = geom[i]
        bx, by = geom[i + 1]
        d = math.hypot(bx - ax, by - ay)
        segs.append((d, ax, ay, bx, by))
        total += d
    if total < min_spacing_world * 0.4:
        return []
    margin = min(total * 0.12, min_spacing_world * 0.4)
    usable = total - 2 * margin
    if usable <= 0:
        targets = [total / 2.0]
    else:
        count = max(1, int(usable / min_spacing_world) + 1)
        if count == 1:
            targets = [total / 2.0]
        else:
            step    = usable / (count - 1)
            targets = [margin + i * step for i in range(count)]
    results = []
    for target in targets:
        acc = 0.0
        for d, ax, ay, bx, by in segs:
            if acc + d >= target or d == 0:
                t   = max(0.0, min(1.0, (target - acc) / d if d > 0 else 0))
                mx  = ax + t * (bx - ax)
                my  = ay + t * (by - ay)
                angle = math.degrees(math.atan2(by - ay, bx - ax))
                if angle > 90 or angle < -90:
                    angle += 180
                results.append((mx, my, angle))
                break
            acc += d
    return results


def as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "y", "on"):
            return True
        if v in ("0", "false", "no", "n", "off", ""):
            return False
    return bool(value)


class Road:
    def __init__(self, name, rtype, speed, lanes, oneway, geom, rid=None,
                 ref="", bridge_level=0, tunnel=False, surface="asphalt",
                 max_weight=0.0, lit=False):
        self.id           = rid or str(uuid.uuid4())
        self.name         = name
        self.rtype        = rtype
        self.speed        = speed
        self.lanes        = lanes
        self.oneway       = oneway
        self.geom         = geom
        self.ref          = ref
        self.bridge_level = bridge_level
        self.tunnel       = tunnel
        self.surface      = surface
        self.max_weight   = max_weight
        self.lit          = lit

    def length(self):
        total = 0.0
        for i in range(len(self.geom) - 1):
            ax, ay = self.geom[i]
            bx, by = self.geom[i + 1]
            total += math.hypot(bx - ax, by - ay)
        return total

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rtype": self.rtype,
            "speed": self.speed,
            "lanes": self.lanes,
            "oneway": self.oneway,
            "geom": self.geom,
            "ref": self.ref,
            "bridge_level": self.bridge_level,
            "tunnel": self.tunnel,
            "surface": self.surface,
            "max_weight": self.max_weight,
            "lit": self.lit,
        }

    @staticmethod
    def from_dict(d):
        if not isinstance(d, dict):
            raise ValueError("Road feature must be an object.")
        rid = d.get("id")
        if not isinstance(rid, str) or not rid.strip():
            rid = str(uuid.uuid4())
        name = d.get("name", "")
        if not isinstance(name, str):
            name = str(name)
        name = name.strip() or "Unnamed"
        rtype = d.get("rtype", "unclassified")
        if rtype not in ROAD_STYLES:
            rtype = "unclassified"
        try:
            speed = int(float(d.get("speed", 50)))
        except (TypeError, ValueError):
            speed = 50
        speed = max(5, min(300, speed))
        try:
            lanes = int(float(d.get("lanes", 1)))
        except (TypeError, ValueError):
            lanes = 1
        lanes = max(1, min(12, lanes))
        geom = []
        for pt in d.get("geom", []) or []:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue
            try:
                x = float(pt[0])
                y = float(pt[1])
            except (TypeError, ValueError):
                continue
            if math.isfinite(x) and math.isfinite(y):
                geom.append([x, y])
        if len(geom) < 2:
            raise ValueError("Road geometry must contain at least two valid points.")
        ref = d.get("ref", "")
        if not isinstance(ref, str):
            ref = str(ref)
        try:
            bridge_level = int(float(d.get("bridge_level", 0)))
        except (TypeError, ValueError):
            bridge_level = 0
        surface = d.get("surface", "asphalt")
        if surface not in SURFACE_TYPES:
            surface = "asphalt"
        try:
            max_weight = float(d.get("max_weight", 0.0))
        except (TypeError, ValueError):
            max_weight = 0.0
        return Road(
            name, rtype, speed, lanes, as_bool(d.get("oneway", False)), geom, rid,
            ref=ref,
            bridge_level=bridge_level,
            tunnel=as_bool(d.get("tunnel", False)),
            surface=surface,
            max_weight=max_weight,
            lit=as_bool(d.get("lit", False)),
        )


class App:
    def __init__(self, root):
        self.root       = root
        self.roads      = {}
        self.current    = []
        self.selected   = None
        self.hover      = None
        self.drag_info  = None
        self.file       = None
        self.dirty      = False
        self.scale      = 1.0
        self.offx       = 0.0
        self.offy       = 0.0
        self.graph      = {}
        self.mode       = "draw"
        self.connectors = []
        self._pending_connector = None
        self.route_path = []
        self.route_start_node = None
        self.route_end_node = None
        self.route_start = None
        self.route_end = None
        self.route_time_hours = 0.0
        self.route_distance_units = 0.0
        self._pan_origin    = None
        self._show_grid     = True
        self._show_nodes    = True
        self._show_names    = True
        self._show_casing   = True
        self._tooltip_win   = None
        self._pending_tip   = None
        self._redraw_queued = False
        self._undo_stack    = []
        self._redo_stack    = []
        self._clipboard     = None
        self._drive_win     = None
        self._drive_canvas  = None
        self._drive_after_id = None
        self._drive_last_tick = None
        self._drive_keys    = set()
        self._drive_pos     = None
        self._drive_heading = 0.0
        self._drive_speed   = 0.0
        self._plugins       = []
        self._plugin_manager_win = None

        root.title(APP_TITLE)
        root.configure(bg=DARK_BG)
        root.geometry("1340x820")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._load_plugins_registry()
        self._build_menu()
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()
        self._bind_keys()
        self.redraw()

    def _build_menu(self):
        mb = tk.Menu(
            self.root, bg=PANEL_BG, fg=PANEL_FG,
            activebackground=ACCENT, activeforeground="white",
            relief="flat", bd=0,
        )
        self.root.config(menu=mb)

        def menu(label, entries):
            m = tk.Menu(mb, tearoff=0, bg=PANEL_BG, fg=PANEL_FG,
                        activebackground=ACCENT, activeforeground="white")
            mb.add_cascade(label=label, menu=m)
            for item in entries:
                if item is None:
                    m.add_separator()
                else:
                    lbl, cmd = item
                    m.add_command(label=lbl, command=cmd)
            return m

        menu("File", [
            ("New              Ctrl+N",       self.new),
            ("Open             Ctrl+O",       self.load),
            ("Save             Ctrl+S",       self.save),
            ("Save As          Ctrl+Shift+S", self.save_as),
            None,
            ("Export JSON",                   self.export_json),
            None,
            ("Quit             Ctrl+Q",       self.on_close),
        ])

        menu("View", [
            ("Zoom In      +",    self.zoom_in),
            ("Zoom Out     -",    self.zoom_out),
            ("Zoom Fit     F",    self.zoom_fit),
            ("Reset View   Home", self.reset_view),
            ("Drive 3D      T",   self.open_drive_mode),
            None,
            ("Toggle Grid   G",   self.toggle_grid),
            ("Toggle Nodes  N",   self.toggle_nodes),
            ("Toggle Labels L",   self.toggle_names),
            ("Toggle Casing C",   self.toggle_casing),
        ])

        menu("Edit", [
            ("Undo             Ctrl+Z",   self.undo),
            ("Redo             Ctrl+Y",   self.redo),
            None,
            ("Copy Feature     Ctrl+C",   self.copy_selected),
            ("Paste Feature    Ctrl+V",   self.paste_road),
            None,
            ("Delete Road      Del",      self.delete_selected),
            ("Remove Last Node Backspace", self.delete_last_node),
            ("Clear Canvas",              self.clear_canvas),
        ])

        menu("Tools", [
            ("Validate Layer File", self.validate_layer_file_dialog),
            ("Run Plugins on Current Layer", self.run_plugins_on_current_layer),
        ])

        menu("Plugins", [
            ("Plugin Manager", self.open_plugin_manager),
            ("Reload Plugin Registry", self._reload_plugins_registry),
            ("Install Built-in Plugins", self.install_builtin_plugins),
        ])

    def _build_toolbar(self):
        tb = tk.Frame(self.root, bg=PANEL_BG, height=44, bd=0,
                      highlightthickness=1, highlightbackground=BORDER)
        tb.pack(side="top", fill="x")
        tb.pack_propagate(False)

        tk.Label(tb, text=" RoadGIS ", bg=PANEL_BG, fg=ACCENT,
                 font=("Consolas", 11, "bold"), padx=6).pack(side="left")

        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", pady=8)

        self._mode_buttons = {}

        for text, mode, key in [("Draw", "draw", "D"), ("Select", "select", "S"), ("Pan", "pan", "P"), ("Route", "route", "R"), ("Connect", "connect", "K")]:
            b = tk.Button(
                tb, text=f"{text} [{key}]",
                command=lambda m=mode: self.set_mode(m),
                bg=PANEL_BG, fg=PANEL_FG, relief="flat",
                font=("Consolas", 9, "bold"),
                activebackground=ACCENT, activeforeground="white",
                padx=12, pady=5, cursor="hand2", bd=0,
            )
            b.pack(side="left", padx=2, pady=6)
            self._mode_buttons[mode] = b

        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", pady=8)

        for text, cmd, fg in [
            ("Fit [F]", self.zoom_fit, PANEL_FG),
            ("Drive 3D [T]", self.open_drive_mode, "#ff8e8e"),
            ("Clear Route", self._clear_route_and_redraw, PANEL_FG),
            ("Delete [Del]", self.delete_selected, ACCENT2),
        ]:
            tk.Button(
                tb, text=text, command=cmd,
                bg=PANEL_BG, fg=fg, relief="flat", font=("Consolas", 9),
                activebackground=ACCENT, activeforeground="white",
                padx=10, pady=5, bd=0, cursor="hand2",
            ).pack(side="left", padx=2, pady=6)

        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", pady=8)

        self._road_count_var = tk.StringVar(value="0")
        tk.Label(tb, text="Features:", bg=PANEL_BG, fg="#6070a0",
                 font=("Consolas", 9)).pack(side="left", padx=(8, 2))
        tk.Label(tb, textvariable=self._road_count_var, bg=PANEL_BG, fg=ACCENT,
                 font=("Consolas", 9, "bold")).pack(side="left")

        tk.Label(tb, text="WGS84 / Custom CRS", bg=PANEL_BG, fg="#2a3a60",
                 font=("Consolas", 8)).pack(side="right", padx=12)

        self._update_mode_buttons()

    def _build_main(self):
        main = tk.Frame(self.root, bg=DARK_BG)
        main.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(main, bg=MAP_BG, bd=0,
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(side="left", fill="both", expand=True)

        self._build_panel(main)

    def _build_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL_BG, width=300, highlightthickness=0)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        tk.Frame(panel, bg="#090d16", width=1).pack(side="left", fill="y")

        inner = tk.Frame(panel, bg=PANEL_BG)
        inner.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(inner, bg="#090d16", height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  LAYER PROPERTIES", bg="#090d16", fg=ACCENT,
                 font=("Consolas", 10, "bold")).pack(side="left", fill="y", padx=2)

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x")

        scroll_canvas = tk.Canvas(inner, bg=PANEL_BG, bd=0,
                                  highlightthickness=0, yscrollincrement=20)
        scrollbar = tk.Scrollbar(inner, orient="vertical",
                                 command=scroll_canvas.yview,
                                 bg=PANEL_BG, troughcolor="#0f1420",
                                 activebackground=ACCENT, width=8)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        body_frame = tk.Frame(scroll_canvas, bg=PANEL_BG)
        body_win = scroll_canvas.create_window((0, 0), window=body_frame, anchor="nw")

        def on_frame_configure(_):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

        def on_canvas_configure(e):
            scroll_canvas.itemconfig(body_win, width=e.width)

        body_frame.bind("<Configure>", on_frame_configure)
        scroll_canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(e):
            if e.num == 4:
                scroll_canvas.yview_scroll(-1, "units")
            elif e.num == 5:
                scroll_canvas.yview_scroll(1, "units")
            else:
                scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        def bind_scroll_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>",   on_mousewheel)
            widget.bind("<Button-5>",   on_mousewheel)
            for child in widget.winfo_children():
                bind_scroll_recursive(child)

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            scroll_canvas.bind(seq, on_mousewheel)
            body_frame.bind(seq, on_mousewheel)

        body = body_frame
        PAD  = 14

        def section_header(text):
            f = tk.Frame(body, bg="#090d16")
            f.pack(fill="x", pady=(10, 0))
            tk.Label(f, text=f"  {text}", bg="#090d16", fg="#6878a8",
                     font=("Consolas", 7, "bold"), pady=4).pack(side="left")
            tk.Frame(body, bg=BORDER, height=1).pack(fill="x")

        def field_label(text):
            tk.Label(body, text=text, bg=PANEL_BG, fg="#5a6a90",
                     font=("Consolas", 7, "bold"), anchor="w").pack(
                     fill="x", padx=PAD, pady=(7, 1))

        def field_entry(var, vcmd=None):
            e = tk.Entry(
                body, bg="#0f1628", fg="#dde4f8", insertbackground=ACCENT,
                relief="flat", font=("Consolas", 10),
                highlightthickness=1, highlightbackground="#1e2a48",
                highlightcolor=ACCENT, textvariable=var,
            )
            if vcmd:
                e.config(validate="key", validatecommand=vcmd)
            e.pack(fill="x", padx=PAD, ipady=5)
            return e

        def two_fields(lbl1, var1, lbl2, var2, vcmd1=None, vcmd2=None):
            row = tk.Frame(body, bg=PANEL_BG)
            row.pack(fill="x", padx=PAD)
            row.columnconfigure(0, weight=1)
            row.columnconfigure(1, weight=1)
            for col, lbl in enumerate([lbl1, lbl2]):
                tk.Label(row, text=lbl, bg=PANEL_BG, fg="#5a6a90",
                         font=("Consolas", 7, "bold"), anchor="w").grid(
                         row=0, column=col, sticky="w", pady=(7, 1),
                         padx=(0, 6) if col == 0 else 0)
            for col, (var, vcmd) in enumerate([(var1, vcmd1), (var2, vcmd2)]):
                e = tk.Entry(row, bg="#0f1628", fg="#dde4f8",
                             insertbackground=ACCENT, relief="flat",
                             font=("Consolas", 10),
                             highlightthickness=1, highlightbackground="#1e2a48",
                             highlightcolor=ACCENT, textvariable=var)
                if vcmd:
                    e.config(validate="key", validatecommand=vcmd)
                e.grid(row=1, column=col, sticky="ew",
                       padx=(0, 6) if col == 0 else 0, ipady=5)

        self._name_var         = tk.StringVar()
        self._ref_var          = tk.StringVar()
        self._speed_var        = tk.StringVar()
        self._lanes_var        = tk.StringVar()
        self._bridge_level_var = tk.StringVar()
        self._max_weight_var   = tk.StringVar()
        self._type_var         = tk.StringVar(value=ROAD_TYPES[0])
        self._surface_var      = tk.StringVar(value="asphalt")
        self._oneway_var       = tk.IntVar()
        self._tunnel_var       = tk.IntVar()
        self._lit_var          = tk.IntVar()

        def int_validate(action, new_val):
            return new_val == "" or new_val.lstrip("-").isdigit()

        def float_validate(action, new_val):
            if new_val in ("", "-", "."):
                return True
            try:
                float(new_val)
                return True
            except ValueError:
                return False

        int_vcmd   = (body.register(int_validate),   "%d", "%P")
        float_vcmd = (body.register(float_validate), "%d", "%P")

        section_header("IDENTIFICATION")
        field_label("FEATURE NAME")
        field_entry(self._name_var)
        field_label("REFERENCE  (e.g. A1, M25)")
        field_entry(self._ref_var)

        section_header("TRAFFIC PROPERTIES")
        two_fields("SPEED LIMIT (km/h)", self._speed_var,
                   "LANES", self._lanes_var,
                   vcmd1=int_vcmd, vcmd2=int_vcmd)

        field_label("ROAD CLASS")
        self._type_var.trace_add("write", self._on_type_change)
        self._type_menu = ttk.Combobox(body, textvariable=self._type_var,
                                       values=ROAD_TYPES, state="readonly",
                                       font=("Consolas", 9))
        self._type_menu.pack(fill="x", padx=PAD)
        self._apply_combo_style()

        self._swatch = tk.Frame(body, bg=ROAD_STYLES[ROAD_TYPES[0]]["color"], height=3)
        self._swatch.pack(fill="x", padx=PAD, pady=(2, 0))

        section_header("PHYSICAL PROPERTIES")
        field_label("SURFACE TYPE")
        self._surface_menu = ttk.Combobox(body, textvariable=self._surface_var,
                                          values=SURFACE_TYPES, state="readonly",
                                          font=("Consolas", 9))
        self._surface_menu.pack(fill="x", padx=PAD)

        two_fields("BRIDGE LEVEL", self._bridge_level_var,
                   "MAX WEIGHT (t)", self._max_weight_var,
                   vcmd1=int_vcmd, vcmd2=float_vcmd)

        section_header("FLAGS")

        def ckbtn(text, var):
            f = tk.Frame(body, bg=PANEL_BG)
            f.pack(fill="x", padx=PAD, pady=2)
            tk.Checkbutton(
                f, text=text, variable=var,
                bg=PANEL_BG, fg="#c0cce8", selectcolor="#1a2a48",
                activebackground=PANEL_BG, activeforeground=ACCENT,
                font=("Consolas", 9), cursor="hand2", relief="flat", bd=0,
            ).pack(side="left")

        ckbtn("One-way  (directional flow)", self._oneway_var)
        ckbtn("Tunnel", self._tunnel_var)
        ckbtn("Street lighting", self._lit_var)

        section_header("ACTIONS")

        bf = tk.Frame(body, bg=PANEL_BG)
        bf.pack(fill="x", padx=PAD, pady=8)
        tk.Button(
            bf, text="Apply Changes", command=self.apply,
            bg=ACCENT, fg="white", relief="flat",
            font=("Consolas", 9, "bold"), activebackground="#3060d0",
            activeforeground="white", padx=10, pady=7, cursor="hand2", bd=0,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(
            bf, text="Delete", command=self.delete_selected,
            bg="#1a0f16", fg=ACCENT2, relief="flat",
            font=("Consolas", 9, "bold"), activebackground=ACCENT2,
            activeforeground="white", padx=10, pady=7, cursor="hand2", bd=0,
        ).pack(side="left", fill="x", expand=True)

        section_header("ATTRIBUTE TABLE")

        self._info_var = tk.StringVar(value="No feature selected")
        tk.Label(body, textvariable=self._info_var, bg=PANEL_BG, fg="#7090b8",
                 font=("Consolas", 8), justify="left", anchor="w",
                 wraplength=260).pack(fill="x", padx=PAD, pady=(6, 4))

        section_header("SYMBOLOGY")

        leg = tk.Frame(body, bg=PANEL_BG)
        leg.pack(fill="x", padx=PAD, pady=6)
        for rtype, style in ROAD_STYLES.items():
            row = tk.Frame(leg, bg=PANEL_BG)
            row.pack(fill="x", pady=2)
            sw = tk.Canvas(row, bg=PANEL_BG, width=36, height=12,
                           highlightthickness=0, bd=0)
            sw.pack(side="left", padx=(0, 8))
            sw.create_rectangle(0, 2, 36, 10, fill=style["casing"], outline="")
            sw.create_rectangle(1, 3, 35,  9, fill=style["color"],  outline="")
            tk.Label(row, text=style["label"], bg=PANEL_BG, fg="#8090b8",
                     font=("Consolas", 8)).pack(side="left")

        section_header("CONTROLS")

        cbody = tk.Frame(body, bg=PANEL_BG)
        cbody.pack(fill="x", padx=PAD, pady=(4, 14))
        controls = [
            ("L-Click",     "Place vertex"),
            ("R-Click",     "Commit feature"),
            ("Backspace",   "Remove last vertex"),
            ("Ctrl+Z",      "Undo"),
            ("Ctrl+Y",      "Redo"),
            ("Ctrl+C",      "Copy selected"),
            ("Ctrl+V",      "Paste feature"),
            ("Drag",        "Move vertex (select mode)"),
            ("Mid-Drag",    "Pan view"),
            ("Scroll",      "Zoom in / out"),
            ("F",           "Fit to features"),
            ("L",           "Toggle labels"),
            ("C",           "Toggle casing"),
            ("N",           "Toggle nodes"),
            ("G",           "Toggle grid"),
            ("Esc",         "Cancel draw"),
            ("R",           "Route mode"),
            ("K",           "Connector mode"),
            ("T",           "Open 3D drive mode"),
            ("Del",         "Delete selected"),
        ]
        for key, desc in controls:
            r = tk.Frame(cbody, bg=PANEL_BG)
            r.pack(fill="x", pady=1)
            tk.Label(r, text=key, bg="#0f1628", fg=ACCENT,
                     font=("Consolas", 8, "bold"), padx=6, pady=2,
                     width=9, anchor="center").pack(side="left")
            tk.Label(r, text="  " + desc, bg=PANEL_BG, fg="#4a5a80",
                     font=("Consolas", 8)).pack(side="left")

        body_frame.update_idletasks()
        bind_scroll_recursive(body_frame)

    def _apply_combo_style(self):
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TCombobox",
                    fieldbackground=INPUT_BG, background=INPUT_BG,
                    foreground=INPUT_FG, selectbackground=ACCENT,
                    selectforeground="white", bordercolor=BORDER,
                    arrowcolor=ACCENT)

    def _on_type_change(self, *_):
        rt = self._type_var.get()
        if rt in ROAD_STYLES:
            self._swatch.config(bg=ROAD_STYLES[rt]["color"])

    def _build_statusbar(self):
        sb = tk.Frame(self.root, bg="#0c1020", height=26,
                      highlightthickness=1, highlightbackground=BORDER)
        sb.pack(side="bottom", fill="x")
        sb.pack_propagate(False)

        self._status_var = tk.StringVar(value="Ready  |  Draw mode")
        self._coords_var = tk.StringVar(value="X: 0.000   Y: 0.000")
        self._zoom_var   = tk.StringVar(value="1:1000")
        self._route_var  = tk.StringVar(value="Route: none")

        tk.Label(sb, text=" RoadGIS ", bg="#1a2860", fg=ACCENT,
                 font=("Consolas", 8, "bold")).pack(side="left")
        tk.Label(sb, textvariable=self._status_var, bg="#0c1020", fg="#7080a0",
                 font=("Consolas", 8), anchor="w", padx=8).pack(side="left")

        tk.Label(sb, textvariable=self._zoom_var, bg="#0c1020", fg="#4a6090",
                 font=("Consolas", 8), padx=10).pack(side="right")
        tk.Frame(sb, bg=BORDER, width=1).pack(side="right", fill="y", pady=4)
        tk.Label(sb, textvariable=self._route_var, bg="#0c1020", fg="#5a7090",
                 font=("Consolas", 8), padx=10).pack(side="right")
        tk.Frame(sb, bg=BORDER, width=1).pack(side="right", fill="y", pady=4)
        tk.Label(sb, textvariable=self._coords_var, bg="#0c1020", fg="#5a7090",
                 font=("Consolas", 8), padx=10).pack(side="right")
        tk.Frame(sb, bg=BORDER, width=1).pack(side="right", fill="y", pady=4)

    def _bind_keys(self):
        c = self.canvas
        c.bind("<Button-1>",        self.on_click)
        c.bind("<Button-3>",        self.on_right_click)
        c.bind("<Motion>",          self.on_mouse_move)
        c.bind("<B1-Motion>",       self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<MouseWheel>",      self.on_scroll)
        c.bind("<Button-4>",        self.on_scroll)
        c.bind("<Button-5>",        self.on_scroll)
        c.bind("<Button-2>",        self.pan_start)
        c.bind("<B2-Motion>",       self.pan_move)
        c.bind("<Leave>",           self._hide_tooltip)

        def guard(fn):
            def _wrapped(_):
                focused = self.root.focus_get()
                if isinstance(focused, (tk.Entry, tk.Text)):
                    return
                fn()
            return _wrapped

        bindings = [
            ("<Control-s>", lambda e: self.save()),
            ("<Control-S>", lambda e: self.save_as()),
            ("<Control-n>", lambda e: self.new()),
            ("<Control-o>", lambda e: self.load()),
            ("<Control-q>", lambda e: self.on_close()),
            ("<Control-z>", lambda e: self.undo()),
            ("<Control-Z>", lambda e: self.undo()),
            ("<Control-y>", lambda e: self.redo()),
            ("<Control-Y>", lambda e: self.redo()),
            ("<Control-c>", lambda e: self.copy_selected()),
            ("<Control-C>", lambda e: self.copy_selected()),
            ("<Control-v>", lambda e: self.paste_road()),
            ("<Control-V>", lambda e: self.paste_road()),
            ("<Control-Shift-P>", lambda e: self.open_plugin_manager()),
            ("<Control-Shift-V>", lambda e: self.validate_layer_file_dialog()),
            ("<Delete>",    guard(self.delete_selected)),
            ("<BackSpace>", guard(self.delete_last_node)),
            ("<Escape>",    guard(self.escape_action)),
            ("<f>",         guard(self.zoom_fit)),
            ("<F>",         guard(self.zoom_fit)),
            ("<g>",         guard(self.toggle_grid)),
            ("<G>",         guard(self.toggle_grid)),
            ("<n>",         guard(self.toggle_nodes)),
            ("<N>",         guard(self.toggle_nodes)),
            ("<l>",         guard(self.toggle_names)),
            ("<L>",         guard(self.toggle_names)),
            ("<c>",         guard(self.toggle_casing)),
            ("<C>",         guard(self.toggle_casing)),
            ("<plus>",      guard(self.zoom_in)),
            ("<equal>",     guard(self.zoom_in)),
            ("<minus>",     guard(self.zoom_out)),
            ("<Home>",      guard(self.reset_view)),
            ("<d>",         guard(lambda: self.set_mode("draw"))),
            ("<D>",         guard(lambda: self.set_mode("draw"))),
            ("<s>",         guard(lambda: self.set_mode("select"))),
            ("<S>",         guard(lambda: self.set_mode("select"))),
            ("<p>",         guard(lambda: self.set_mode("pan"))),
            ("<P>",         guard(lambda: self.set_mode("pan"))),
            ("<r>",         guard(lambda: self.set_mode("route"))),
            ("<R>",         guard(lambda: self.set_mode("route"))),
            ("<k>",         guard(lambda: self.set_mode("connect"))),
            ("<K>",         guard(lambda: self.set_mode("connect"))),
            ("<t>",         guard(self.open_drive_mode)),
            ("<T>",         guard(self.open_drive_mode)),
        ]
        for seq, handler in bindings:
            self.root.bind(seq, handler)

    def set_mode(self, mode):
        self.mode    = mode
        self.current = []
        if mode != "route":
            self._clear_route()
        if mode != "connect":
            self._pending_connector = None
        cursors = {"draw": "crosshair", "select": "arrow", "pan": "fleur", "route": "tcross", "connect": "crosshair"}
        self.canvas.config(cursor=cursors.get(mode, "arrow"))
        self._update_mode_buttons()
        if mode == "route":
            self._set_status("Route mode active  |  Click start and destination")
        elif mode == "connect":
            self._set_status("Connect mode active  |  Click two vertices to build a connector/interchange")
        else:
            self._set_status(f"{mode.capitalize()} mode active")
        self.redraw()

    def escape_action(self):
        if self.mode == "route":
            self._clear_route_and_redraw()
            self._set_status("Route cleared")
            return
        if self.mode == "connect":
            self._pending_connector = None
            self.redraw()
            self._set_status("Connector selection canceled")
            return
        self.cancel_draw()

    def _update_mode_buttons(self):
        for m, btn in self._mode_buttons.items():
            active = m == self.mode
            btn.config(
                bg=ACCENT if active else PANEL_BG,
                fg="white" if active else PANEL_FG,
            )

    def world(self, x, y):
        return ((x - self.offx) / self.scale, (y - self.offy) / self.scale)

    def screen(self, x, y):
        return (x * self.scale + self.offx, y * self.scale + self.offy)

    def snap(self, p):
        threshold = SNAP_PX / self.scale
        best, best_d = None, threshold
        for r in self.roads.values():
            for pt in r.geom:
                d = math.hypot(p[0] - pt[0], p[1] - pt[1])
                if d < best_d:
                    best_d = d
                    best   = pt
        return best if best else p

    def on_click(self, e):
        if self.mode == "pan":
            self.pan_start(e)
            return
        wx, wy = self.world(e.x, e.y)
        if self.mode == "route":
            self._route_click((wx, wy))
            return
        if self.mode == "connect":
            self._connector_click((wx, wy))
            return
        if self.mode == "select":
            hit, idx = self._hit_test(wx, wy)
            if hit:
                self.selected  = hit
                self.drag_info = (hit, idx)
                self.load_fields(hit)
                self._update_info(hit)
            else:
                self.selected  = None
                self.drag_info = None
                self._info_var.set("No feature selected")
            self.redraw()
            return
        p = self.snap((wx, wy))
        self.current.append(list(p))
        self.dirty = True
        self._set_status(
            f"Drawing  {len(self.current)} vertices  |  Right-click to commit"
        )
        self.redraw()

    def _hit_test(self, wx, wy):
        threshold = SNAP_PX / self.scale
        best_road = None
        best_idx  = None
        best_dist = float("inf")
        for r in self.roads.values():
            for i, pt in enumerate(r.geom):
                d = math.hypot(wx - pt[0], wy - pt[1])
                if d < threshold and d < best_dist:
                    best_dist = d
                    best_road = r
                    best_idx  = i
            if best_road is None:
                for i in range(len(r.geom) - 1):
                    ax, ay = r.geom[i]
                    bx, by = r.geom[i + 1]
                    d = self._pt_seg(wx, wy, ax, ay, bx, by)
                    if d < threshold * 2 and d < best_dist:
                        best_dist = d
                        best_road = r
                        best_idx  = None
        return best_road, best_idx

    def _pt_seg(self, px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def on_right_click(self, e):
        if self.mode == "route":
            self._clear_route_and_redraw()
            self._set_status("Route cleared")
            return
        if self.mode == "connect":
            self._pending_connector = None
            self.redraw()
            self._set_status("Connector selection canceled")
            return
        if self.mode == "draw" and len(self.current) > 1:
            self._push_undo()
            name  = self._name_var.get().strip() or "Unnamed"
            rtype = self._type_var.get() or "unclassified"
            try:
                speed = int(self._speed_var.get())
            except ValueError:
                speed = 50
            try:
                lanes = int(self._lanes_var.get())
            except ValueError:
                lanes = 1
            try:
                bridge_level = int(self._bridge_level_var.get())
            except ValueError:
                bridge_level = 0
            try:
                max_weight = float(self._max_weight_var.get())
            except ValueError:
                max_weight = 0.0

            r = Road(
                name, rtype, speed, lanes, bool(self._oneway_var.get()),
                [list(p) for p in self.current],
                ref=self._ref_var.get(),
                bridge_level=bridge_level,
                tunnel=bool(self._tunnel_var.get()),
                surface=self._surface_var.get(),
                max_weight=max_weight,
                lit=bool(self._lit_var.get()),
            )
            self.roads[r.id] = r
            self.build_graph()
            self._road_count_var.set(str(len(self.roads)))
            self._set_status(f"Feature '{name}' committed  -  {len(self.roads)} total")
        self.current = []
        self.redraw()

    def on_mouse_move(self, e):
        wx, wy = self.world(e.x, e.y)
        self._coords_var.set(f"X: {wx:,.1f}   Y: {wy:,.1f}")

        if self.mode == "select":
            road, _ = self._hit_test(wx, wy)
            if road is not self.hover:
                self.hover = road
                self.redraw()
                if road:
                    self._schedule_tooltip(road, e.x_root, e.y_root)
                else:
                    self._hide_tooltip()
        else:
            if self.hover is not None:
                self.hover = None
                self.redraw()

        if self.current and self.mode == "draw":
            self.redraw()
            lx, ly = self.screen(*self.current[-1])
            self.canvas.create_line(lx, ly, e.x, e.y,
                                    dash=(5, 4), fill=ACCENT,
                                    width=1.5, tags="preview")

    def on_drag(self, e):
        if self.mode == "pan":
            self.pan_move(e)
            return
        if self.mode == "select" and self.drag_info:
            road, idx = self.drag_info
            if idx is not None:
                if not getattr(self, "_drag_undo_pushed", False):
                    self._push_undo()
                    self._drag_undo_pushed = True
                wx, wy     = self.world(e.x, e.y)
                old_pt = tuple(road.geom[idx])
                new_pt = tuple(self.snap((wx, wy)))
                road.geom[idx] = [new_pt[0], new_pt[1]]
                level = int(road.bridge_level)
                for conn in self.connectors:
                    if tuple(conn["a"]) == (old_pt[0], old_pt[1], level):
                        conn["a"] = [new_pt[0], new_pt[1], level]
                    if tuple(conn["b"]) == (old_pt[0], old_pt[1], level):
                        conn["b"] = [new_pt[0], new_pt[1], level]
                self.dirty = True
                self.build_graph()
                self.redraw()

    def on_release(self, e):
        if self.mode in ("select", "pan"):
            self.drag_info        = None
            self._pan_origin      = None
            self._drag_undo_pushed = False

    def on_scroll(self, e):
        if hasattr(e, "delta") and e.delta != 0:
            factor = 1.12 if e.delta > 0 else 1 / 1.12
        elif e.num == 4:
            factor = 1.12
        else:
            factor = 1 / 1.12
        self.offx  = e.x - (e.x - self.offx) * factor
        self.offy  = e.y - (e.y - self.offy) * factor
        self.scale *= factor
        self._update_zoom_label()
        self.redraw()

    def pan_start(self, e):
        self._pan_origin = (e.x, e.y, self.offx, self.offy)

    def pan_move(self, e):
        if self._pan_origin:
            ox, oy, bx, by = self._pan_origin
            self.offx = bx + (e.x - ox)
            self.offy = by + (e.y - oy)
            self.redraw()

    def _update_zoom_label(self):
        approx = int(1000 / max(self.scale, 0.001))
        self._zoom_var.set(f"1:{approx:,}")

    def zoom_in(self):
        cx = self.canvas.winfo_width()  / 2
        cy = self.canvas.winfo_height() / 2
        self.offx  = cx - (cx - self.offx) * 1.2
        self.offy  = cy - (cy - self.offy) * 1.2
        self.scale *= 1.2
        self._update_zoom_label()
        self.redraw()

    def zoom_out(self):
        cx = self.canvas.winfo_width()  / 2
        cy = self.canvas.winfo_height() / 2
        self.offx  = cx - (cx - self.offx) / 1.2
        self.offy  = cy - (cy - self.offy) / 1.2
        self.scale /= 1.2
        self._update_zoom_label()
        self.redraw()

    def zoom_fit(self):
        if not self.roads:
            self.reset_view()
            return
        all_pts = [pt for r in self.roads.values() for pt in r.geom]
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        w   = self.canvas.winfo_width()  or 900
        h   = self.canvas.winfo_height() or 600
        pad = 100
        dx  = maxx - minx or 1
        dy  = maxy - miny or 1
        self.scale = min((w - pad * 2) / dx, (h - pad * 2) / dy)
        self.offx  = pad - minx * self.scale
        self.offy  = pad - miny * self.scale
        self._update_zoom_label()
        self.redraw()

    def reset_view(self):
        self.scale = 1.0
        self.offx  = 0.0
        self.offy  = 0.0
        self._update_zoom_label()
        self.redraw()

    def toggle_grid(self):
        self._show_grid = not self._show_grid
        self.redraw()

    def toggle_nodes(self):
        self._show_nodes = not self._show_nodes
        self.redraw()

    def toggle_names(self):
        self._show_names = not self._show_names
        self.redraw()

    def toggle_casing(self):
        self._show_casing = not self._show_casing
        self.redraw()

    def cancel_draw(self):
        self.current = []
        self._set_status("Draw cancelled")
        self.redraw()

    def delete_last_node(self):
        if self.current:
            self.current.pop()
            self._set_status(
                f"Removed vertex  -  {len(self.current)} remaining"
            )
            self.redraw()

    def _schedule_tooltip(self, road, rx, ry):
        self._hide_tooltip()
        self._pending_tip = road
        self.root.after(500, lambda: self._show_tooltip_if_pending(road, rx, ry))

    def _show_tooltip_if_pending(self, road, rx, ry):
        if self._pending_tip is not road:
            return
        if self.hover is not road:
            return
        if self._tooltip_win:
            return
        style    = ROAD_STYLES.get(road.rtype, {})
        name_str = road.name or "Unnamed"
        if road.ref:
            name_str = f"[{road.ref}]  {name_str}"
        tip_flags = []
        if road.tunnel:
            tip_flags.append("tunnel")
        if road.lit:
            tip_flags.append("lit")
        if road.bridge_level:
            tip_flags.append(f"bridge L{road.bridge_level}")
        lines = [
            (name_str, ACCENT, 9, True),
            (f"{style.get('label', '?')}  |  {road.speed} km/h  |  {road.surface}", "#8090c0", 8, False),
            (f"{road.lanes} lane{'s' if road.lanes != 1 else ''}  |  {'One-way' if road.oneway else 'Two-way'}", "#6070a0", 8, False),
            (f"Length: {road.length():.0f} u" + (f"  |  max {road.max_weight}t" if road.max_weight else ""), "#6070a0", 8, False),
        ]
        if tip_flags:
            lines.append(("  ".join(tip_flags), "#4a9060", 8, False))
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{rx + 14}+{ry + 14}")
        tip.configure(bg=BORDER)
        inner = tk.Frame(tip, bg="#0f1828", padx=10, pady=7)
        inner.pack(padx=1, pady=1)
        for text, fg, sz, bold in lines:
            tk.Label(inner, text=text, bg="#0f1828", fg=fg,
                     font=("Consolas", sz, "bold" if bold else "normal"),
                     anchor="w").pack(fill="x")
        sw = tk.Canvas(inner, bg="#0f1828", width=80, height=6,
                       highlightthickness=0, bd=0)
        sw.pack(fill="x", pady=(4, 0))
        col = style.get("color", "#888")
        cas = style.get("casing", "#333")
        sw.create_rectangle(0, 1, 80, 5, fill=cas, outline="")
        sw.create_rectangle(1, 2, 79, 4, fill=col, outline="")
        self._tooltip_win = tip

    def _hide_tooltip(self, *_):
        self._pending_tip = None
        if self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except tk.TclError:
                pass
            self._tooltip_win = None

    def _geoms_to_flat_screen(self, geom):
        flat = []
        for pt in geom:
            sx, sy = self.screen(*pt)
            flat.extend([sx, sy])
        return flat

    def redraw(self):
        c = self.canvas
        c.delete("all")

        w = c.winfo_width()  or 1200
        h = c.winfo_height() or 800
        c.create_rectangle(0, 0, w, h, fill=MAP_BG, outline="")

        if self._show_grid:
            self._draw_grid()

        road_order = sorted(
            self.roads.values(),
            key=lambda r: ROAD_STYLES.get(r.rtype, {}).get("width", 2),
        )

        if self._show_casing:
            for r in road_order:
                style   = ROAD_STYLES.get(r.rtype, {"casing": "#222", "width": 2})
                w_px    = style["width"] * max(0.6, self.scale ** 0.32) + 2.5
                flat    = self._geoms_to_flat_screen(smooth_geom(r.geom))
                if len(flat) >= 4:
                    c.create_line(*flat, width=w_px, fill=style["casing"],
                                  capstyle="round", joinstyle="round")

        for r in road_order:
            is_sel   = r is self.selected
            is_hover = r is self.hover
            style    = ROAD_STYLES.get(r.rtype, {"color": "#aaa", "width": 2})
            color    = style["color"]
            width    = style["width"] * max(0.6, self.scale ** 0.32)
            draw_pts = smooth_geom(r.geom)
            flat     = self._geoms_to_flat_screen(draw_pts)

            if len(flat) < 4:
                continue

            if is_sel or is_hover:
                hi_col = SELECT_COL if is_sel else HOVER_COL
                c.create_line(*flat, width=width + 8, fill=hi_col,
                              capstyle="round", joinstyle="round")

            if r.bridge_level > 0:
                elev_col = (
                    "#007a99" if r.bridge_level == 1
                    else "#996600" if r.bridge_level == 2
                    else "#992222"
                )
                c.create_line(*flat, width=width + 5, fill=elev_col,
                              capstyle="round", joinstyle="round")

            dash_args = {}
            if r.tunnel:
                dash_args["dash"] = (int(max(4, width * 1.5)), int(max(3, width)))

            c.create_line(*flat, width=width, fill=color,
                          capstyle="round", joinstyle="round", **dash_args)

            if r.surface in ("gravel", "dirt"):
                c.create_line(*flat, width=max(1, width * 0.4), fill="#ffffff22",
                              capstyle="round", joinstyle="round",
                              dash=(2, int(max(4, width * 2))))

            if r.oneway:
                self._draw_oneway_arrows(c, draw_pts, width)

            if self._show_nodes:
                r_px = NODE_RADIUS * (1.7 if is_sel else 1.0)
                nc   = SELECT_COL if is_sel else color
                for nx, ny in r.geom:
                    sx, sy = self.screen(nx, ny)
                    c.create_oval(sx - r_px, sy - r_px, sx + r_px, sy + r_px,
                                  fill=MAP_BG, outline=nc, width=1.5)

        for conn in self.connectors:
            ax, ay, al = conn["a"]
            bx, by, bl = conn["b"]
            x1, y1 = self.screen(ax, ay)
            x2, y2 = self.screen(bx, by)
            c.create_line(x1, y1, x2, y2, fill="#7de2d1", width=2, dash=(6, 4))
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            c.create_text(mx, my - 8, text=self._connector_text(conn), fill="#9aeede", font=("Consolas", 7, "bold"))

        if self._pending_connector is not None:
            px, py, pl = self._pending_connector
            sx, sy = self.screen(px, py)
            c.create_oval(sx - 8, sy - 8, sx + 8, sy + 8, fill="#7de2d1", outline="white", width=1.5)
            c.create_text(sx, sy - 12, text=f"L{pl}", fill="#9aeede", font=("Consolas", 7, "bold"))

        if len(self.route_path) > 1:
            flat = []
            for pt in self.route_path:
                sx, sy = self.screen(*pt)
                flat.extend([sx, sy])
            c.create_line(*flat, width=7, fill="#ffffff", capstyle="round", joinstyle="round")
            c.create_line(*flat, width=4, fill=ACCENT2, capstyle="round", joinstyle="round")

        if self.route_start is not None:
            sx, sy = self.screen(*self.route_start)
            c.create_oval(sx - 7, sy - 7, sx + 7, sy + 7, fill="#19c37d", outline="white", width=1.5)
        if self.route_end is not None:
            sx, sy = self.screen(*self.route_end)
            c.create_oval(sx - 7, sy - 7, sx + 7, sy + 7, fill="#f0b90b", outline="white", width=1.5)

        if self._show_names:
            for r in road_order:
                name = r.name
                if not name or name == "Unnamed":
                    continue
                smooth_pts = smooth_geom(r.geom)
                min_spacing = max(60, 180 / max(self.scale, 0.01))
                positions = label_positions(
                    [(p[0], p[1]) for p in smooth_pts],
                    min_spacing_world=min_spacing,
                )
                font_size = max(7, min(14, int(9 * self.scale ** 0.2)))
                font_spec = ("Consolas", font_size, "bold")
                for wx, wy, angle in positions:
                    sx, sy = self.screen(wx, wy)
                    for dx, dy, col in ((-1, 1, "#080e18"), (1, 1, "#080e18"),
                                        (0, 2, "#080e18"), (0, 0, PANEL_FG)):
                        c.create_text(sx + dx, sy + dy, text=name, fill=col,
                                      font=font_spec, angle=angle, anchor="center")

        if len(self.current) > 1:
            for i in range(len(self.current) - 1):
                x1, y1 = self.screen(*self.current[i])
                x2, y2 = self.screen(*self.current[i + 1])
                c.create_line(x1, y1, x2, y2, width=2, fill=ACCENT,
                              dash=(8, 4), capstyle="round")

        for pt in self.current:
            sx, sy = self.screen(*pt)
            c.create_oval(sx - 5, sy - 5, sx + 5, sy + 5,
                          fill=ACCENT, outline="white", width=1)

        self._draw_scale_bar()
        self._draw_north_arrow()

    def _draw_oneway_arrows(self, c, draw_pts, width):
        acc = 0.0
        for i in range(len(draw_pts) - 1):
            x1, y1 = self.screen(*draw_pts[i])
            x2, y2 = self.screen(*draw_pts[i + 1])
            seg_px  = math.hypot(x2 - x1, y2 - y1)
            acc    += seg_px
            if acc >= 60:
                acc  = 0.0
                mx   = (x1 + x2) / 2
                my   = (y1 + y2) / 2
                ang  = math.atan2(y2 - y1, x2 - x1)
                al   = 7
                ax2  = mx + al * math.cos(ang)
                ay2  = my + al * math.sin(ang)
                lx2  = mx - al * 0.5 * math.cos(ang - 0.5)
                ly2  = my - al * 0.5 * math.sin(ang - 0.5)
                rx2  = mx - al * 0.5 * math.cos(ang + 0.5)
                ry2  = my - al * 0.5 * math.sin(ang + 0.5)
                c.create_polygon(ax2, ay2, lx2, ly2, rx2, ry2,
                                 fill="white", outline="")

    def _draw_grid(self):
        c = self.canvas
        w = c.winfo_width()  or 1200
        h = c.winfo_height() or 800

        step_world = 1
        for candidate in [1, 5, 10, 25, 50, 100, 200, 500, 1000, 2000, 5000]:
            if candidate * self.scale > 60:
                step_world = candidate
                break

        step_px = step_world * self.scale

        x0 = self.offx % step_px
        xi = math.floor(-self.offx / step_px)
        while x0 < w:
            wx_val = xi * step_world
            c.create_line(x0, 0, x0, h, fill=GRID_COL, width=1)
            if self.scale > 0.25:
                c.create_text(x0 + 3, h - 14, text=f"{wx_val:.0f}",
                              fill=GRID_LABEL, font=("Consolas", 7), anchor="sw")
            x0 += step_px
            xi += 1

        y0 = self.offy % step_px
        yi = math.floor(-self.offy / step_px)
        while y0 < h:
            wy_val = yi * step_world
            c.create_line(0, y0, w, y0, fill=GRID_COL, width=1)
            if self.scale > 0.25:
                c.create_text(4, y0 - 3, text=f"{wy_val:.0f}",
                              fill=GRID_LABEL, font=("Consolas", 7), anchor="sw")
            y0 += step_px
            yi += 1

        ox, oy = self.screen(0, 0)
        c.create_line(ox, 0, ox, h, fill="#2a3860", width=1)
        c.create_line(0, oy, w, oy, fill="#2a3860", width=1)

    def _draw_scale_bar(self):
        c = self.canvas
        h = c.winfo_height() or 700

        target_px  = 100.0
        world_dist = target_px / self.scale
        for nice in [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 2000, 5000, 10000]:
            if nice >= world_dist * 0.5:
                world_dist = nice
                break
        bar_px = world_dist * self.scale

        bx = 20
        by = h - 38
        bh = 5

        c.create_rectangle(bx - 1, by - 1, bx + bar_px + 1, by + bh + 1,
                           fill="#0a0f1c", outline="")
        c.create_rectangle(bx, by, bx + bar_px / 2, by + bh,
                           fill="#7080a0", outline="")
        c.create_rectangle(bx + bar_px / 2, by, bx + bar_px, by + bh,
                           fill="#303858", outline="")
        c.create_text(bx, by - 4, text="0",
                      fill=GRID_LABEL, font=("Consolas", 7), anchor="sw")
        c.create_text(bx + bar_px, by - 4, text=f"{world_dist:.0f} u",
                      fill=GRID_LABEL, font=("Consolas", 7), anchor="se")

    def _draw_north_arrow(self):
        c  = self.canvas
        w  = c.winfo_width() or 1000
        nx = w - 36
        ny = 50
        r  = 16

        c.create_oval(nx - r - 2, ny - r - 2, nx + r + 2, ny + r + 2,
                      fill="#0a0f1c", outline="#1e2840", width=1)
        c.create_polygon(nx, ny - r + 2, nx - 5, ny + 4, nx, ny - 2,
                         fill=ACCENT, outline="")
        c.create_polygon(nx, ny - r + 2, nx + 5, ny + 4, nx, ny - 2,
                         fill="#2a3a60", outline="")
        c.create_polygon(nx, ny + r - 2, nx - 5, ny - 4, nx, ny + 2,
                         fill="#3a4a70", outline="")
        c.create_polygon(nx, ny + r - 2, nx + 5, ny - 4, nx, ny + 2,
                         fill="#2a3050", outline="")
        c.create_text(nx, ny - r - 6, text="N", fill=ACCENT,
                      font=("Consolas", 8, "bold"), anchor="s")

    def _snapshot(self):
        return copy.deepcopy({
            "roads": [r.to_dict() for r in self.roads.values()],
            "connectors": self.connectors,
        })

    def _push_undo(self):
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > 64:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore_snapshot(self, snapshot):
        self.roads    = {}
        self.connectors = []
        payload = snapshot if isinstance(snapshot, dict) else {"roads": snapshot, "connectors": []}
        self.selected = None
        self.drag_info = None
        for d in payload.get("roads", []):
            try:
                r = Road.from_dict(d)
            except (ValueError, TypeError):
                continue
            self.roads[r.id] = r
        self.connectors = self._normalize_connectors(payload.get("connectors", []))
        self.build_graph()
        self._road_count_var.set(str(len(self.roads)))
        self._info_var.set("No feature selected")
        self.dirty = True
        self.redraw()

    def undo(self):
        if not self._undo_stack:
            self._set_status("Nothing to undo")
            return
        self._redo_stack.append(self._snapshot())
        snapshot = self._undo_stack.pop()
        self._restore_snapshot(snapshot)
        self._set_status(f"Undo  -  {len(self._undo_stack)} steps remain")

    def redo(self):
        if not self._redo_stack:
            self._set_status("Nothing to redo")
            return
        self._undo_stack.append(self._snapshot())
        snapshot = self._redo_stack.pop()
        self._restore_snapshot(snapshot)
        self._set_status(f"Redo  -  {len(self._redo_stack)} steps remain")

    def copy_selected(self):
        if not self.selected:
            self._set_status("Nothing selected to copy")
            return
        self._clipboard = copy.deepcopy(self.selected.to_dict())
        self._set_status(f"Copied '{self.selected.name}'")

    def paste_road(self):
        if not self._clipboard:
            self._set_status("Clipboard is empty")
            return
        self._push_undo()
        d         = copy.deepcopy(self._clipboard)
        d["id"]   = str(uuid.uuid4())
        d["name"] = d["name"] + " (copy)"
        offset    = 20 / self.scale
        d["geom"] = [[p[0] + offset, p[1] + offset] for p in d["geom"]]
        r = Road.from_dict(d)
        self.roads[r.id] = r
        self.selected = r
        self.load_fields(r)
        self._update_info(r)
        self.build_graph()
        self._road_count_var.set(str(len(self.roads)))
        self.dirty = True
        self.redraw()
        self._set_status(f"Pasted '{r.name}'")

    def build_graph(self):
        self._prune_orphan_connectors()
        self.graph = {}
        for r in self.roads.values():
            for i in range(len(r.geom) - 1):
                a = (r.geom[i][0], r.geom[i][1], int(r.bridge_level))
                b = (r.geom[i + 1][0], r.geom[i + 1][1], int(r.bridge_level))
                seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
                edge_h = self._segment_travel_hours(r, seg_len)
                self.graph.setdefault(a, []).append((b, edge_h))
                self.graph.setdefault(b, [])
                if not r.oneway:
                    self.graph.setdefault(b, []).append((a, edge_h))
        for conn in self.connectors:
            try:
                a = tuple(conn["a"])
                b = tuple(conn["b"])
            except Exception:
                continue
            if a in self.graph and b in self.graph:
                self.graph[a].append((b, CONNECTOR_TRAVEL_HOURS))
                self.graph[b].append((a, CONNECTOR_TRAVEL_HOURS))
        self._clear_route()

    def _segment_travel_hours(self, road, seg_len):
        base_speed = max(5.0, float(road.speed))
        lane_factor = 1.0 + min(0.2, max(0, road.lanes - 1) * 0.05)
        surface_factor = {"asphalt": 1.0, "gravel": 0.78, "dirt": 0.62}.get(road.surface, 0.9)
        tunnel_factor = 0.92 if road.tunnel else 1.0
        lit_factor = 1.03 if road.lit else 1.0
        effective_speed = max(5.0, base_speed * lane_factor * surface_factor * tunnel_factor * lit_factor)
        distance_km = max(0.001, seg_len / 1000.0)
        return distance_km / effective_speed

    def _valid_level_nodes(self):
        nodes = set()
        for r in self.roads.values():
            level = int(r.bridge_level)
            for vx, vy in r.geom:
                nodes.add((vx, vy, level))
        return nodes

    def _coerce_level_node(self, node):
        if not isinstance(node, (list, tuple)) or len(node) != 3:
            return None
        try:
            return [float(node[0]), float(node[1]), int(node[2])]
        except (TypeError, ValueError):
            return None

    def _connector_level_span(self, a, b):
        return f"{int(a[2])}-{int(b[2])}"

    def _build_connector(self, a, b):
        kind = "interchange" if int(a[2]) != int(b[2]) else "connector"
        return {
            "a": [a[0], a[1], int(a[2])],
            "b": [b[0], b[1], int(b[2])],
            "kind": kind,
            "level_span": self._connector_level_span(a, b),
        }

    def _connector_text(self, conn):
        try:
            a = conn["a"]
            b = conn["b"]
            kind = conn.get("kind", "connector")
            span = conn.get("level_span") or self._connector_level_span(a, b)
        except Exception:
            return "Connector"
        if kind == "interchange":
            return f"I/C {span}"
        return f"L{int(a[2])}<->L{int(b[2])}"

    def _normalize_connectors(self, connectors):
        normalized = []
        for conn in connectors or []:
            if not isinstance(conn, dict):
                continue
            a = self._coerce_level_node(conn.get("a"))
            b = self._coerce_level_node(conn.get("b"))
            if not a or not b or a == b:
                continue
            normalized.append(self._build_connector(a, b))
        return normalized

    def _prune_orphan_connectors(self):
        valid = self._valid_level_nodes()
        before = len(self.connectors)
        kept = []
        for conn in self.connectors:
            try:
                a = tuple(conn["a"])
                b = tuple(conn["b"])
            except Exception:
                continue
            if a in valid and b in valid and a != b:
                kept.append(conn)
        self.connectors = kept
        return before - len(kept)

    def _nearest_graph_node(self, p):
        if not self.graph:
            return None, None
        best = None
        best_d = float("inf")
        for node in self.graph.keys():
            d = math.hypot(node[0] - p[0], node[1] - p[1])
            if d < best_d:
                best_d = d
                best = node
        return best, best_d

    def _shortest_time_path(self, start, end):
        if start not in self.graph or end not in self.graph:
            return None, None
        dist = {start: 0.0}
        prev = {}
        pq = [(0.0, start)]
        seen = set()
        while pq:
            curr_d, node = heapq.heappop(pq)
            if node in seen:
                continue
            seen.add(node)
            if node == end:
                break
            for nxt, w in self.graph.get(node, []):
                nd = curr_d + w
                if nd < dist.get(nxt, float("inf")):
                    dist[nxt] = nd
                    prev[nxt] = node
                    heapq.heappush(pq, (nd, nxt))
        if end not in dist:
            return None, None
        path = [end]
        cur = end
        while cur != start:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path, dist[end]

    def _run_json_process(self, cmd, payload, timeout=8):
        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=True,
                timeout=timeout,
            )
            raw = proc.stdout.strip()
            if not raw:
                return None
            return json.loads(raw)
        except (subprocess.SubprocessError, OSError, ValueError, json.JSONDecodeError):
            return None

    def _shortest_time_path_polyglot(self, start, end):
        if start not in self.graph or end not in self.graph:
            return None, None
        adjacency = []
        for node, edges in self.graph.items():
            adjacency.append({
                "node": [node[0], node[1], int(node[2])],
                "edges": [{"to": [n[0], n[1], int(n[2])], "weight": float(w)} for n, w in edges],
            })
        payload = {
            "start": [start[0], start[1], int(start[2])],
            "end": [end[0], end[1], int(end[2])],
            "graph": adjacency,
        }
        cmd = None
        if os.path.exists(RUST_ROUTER_BIN):
            cmd = [RUST_ROUTER_BIN]
        elif os.path.exists(RUST_ROUTER_MANIFEST) and shutil.which("cargo"):
            cmd = ["cargo", "run", "--quiet", "--release", "--manifest-path", RUST_ROUTER_MANIFEST]
        if not cmd:
            return None, None
        out = self._run_json_process(cmd, payload)
        if not isinstance(out, dict):
            return None, None
        raw_path = out.get("path")
        travel_h = out.get("travel_hours")
        if not isinstance(raw_path, list) or not isinstance(travel_h, (int, float)):
            return None, None
        parsed = []
        for n in raw_path:
            if not isinstance(n, (list, tuple)) or len(n) != 3:
                return None, None
            try:
                parsed.append((float(n[0]), float(n[1]), int(n[2])))
            except (TypeError, ValueError):
                return None, None
        return parsed, float(travel_h)

    def _format_hours(self, hours):
        total_mins = max(0, int(round(hours * 60)))
        h = total_mins // 60
        m = total_mins % 60
        if h:
            return f"{h}h {m}m"
        return f"{m}m"

    def _route_length_units(self, path):
        total = 0.0
        for i in range(len(path) - 1):
            a = path[i]
            b = path[i + 1]
            total += math.hypot(b[0] - a[0], b[1] - a[1])
        return total

    def _update_route_status_label(self):
        if len(self.route_path) > 1:
            km = self.route_distance_units / 1000.0
            self._route_var.set(f"Route: {km:.2f} km | {self._format_hours(self.route_time_hours)}")
        elif self.route_start is not None:
            self._route_var.set("Route: start set")
        else:
            self._route_var.set("Route: none")

    def _clear_route(self):
        self.route_path = []
        self.route_start_node = None
        self.route_end_node = None
        self.route_start = None
        self.route_end = None
        self.route_time_hours = 0.0
        self.route_distance_units = 0.0
        self._update_route_status_label()

    def _clear_route_and_redraw(self):
        self._clear_route()
        self.redraw()

    def _route_click(self, p):
        if not self.graph:
            self._set_status("No road network available for routing")
            return
        node, dist_to_node = self._nearest_road_vertex_with_level(p)
        if node is None:
            self._set_status("No routable nodes found")
            return
        if node not in self.graph:
            self._set_status("Selected node is not part of routable graph")
            return
        max_pick_dist = ROUTE_PICK_PX / max(self.scale, 0.001)
        if dist_to_node is not None and dist_to_node > max_pick_dist:
            self._set_status("Click closer to a road vertex to set route point")
            return
        if self.route_start is None or (self.route_start is not None and self.route_end is not None):
            self.route_start_node = node
            self.route_start = (node[0], node[1])
            self.route_end_node = None
            self.route_end = None
            self.route_path = []
            self.route_time_hours = 0.0
            self.route_distance_units = 0.0
            self._update_route_status_label()
            self._set_status("Start set  |  Click destination")
            self.redraw()
            return
        self.route_end_node = node
        self.route_end = (node[0], node[1])
        path_nodes, travel_h = self._shortest_time_path_polyglot(self.route_start_node, self.route_end_node)
        if not path_nodes:
            path_nodes, travel_h = self._shortest_time_path(self.route_start_node, self.route_end_node)
        path = [(n[0], n[1]) for n in path_nodes] if path_nodes else None
        if not path:
            self.route_path = []
            self.route_time_hours = 0.0
            self.route_distance_units = 0.0
            self._update_route_status_label()
            self._set_status("No route found between selected points")
            self.redraw()
            return
        self.route_path = path
        self.route_time_hours = travel_h
        self.route_distance_units = self._route_length_units(path)
        self._update_route_status_label()
        km = self.route_distance_units / 1000.0
        self._set_status(f"Fastest route: {self._format_hours(travel_h)} over {km:.2f} km")
        self.redraw()

    def _nearest_road_vertex_with_level(self, p):
        best = None
        best_d = float("inf")
        for r in self.roads.values():
            level = int(r.bridge_level)
            for vx, vy in r.geom:
                d = math.hypot(vx - p[0], vy - p[1])
                if d < best_d:
                    best_d = d
                    best = (vx, vy, level)
        return best, best_d

    def _connector_click(self, p):
        if not self.roads:
            self._set_status("No roads available for connectors")
            return
        node, dist_to_node = self._nearest_road_vertex_with_level(p)
        if node is None:
            self._set_status("No vertex found")
            return
        max_pick_dist = CONNECT_PICK_PX / max(self.scale, 0.001)
        if dist_to_node is not None and dist_to_node > max_pick_dist:
            self._set_status("Click closer to a road vertex for connector endpoint")
            return
        if self._pending_connector is None:
            self._pending_connector = node
            self._set_status(f"Connector start set at L{node[2]}  |  Click second vertex")
            self.redraw()
            return
        a = tuple(self._pending_connector)
        b = tuple(node)
        if a == b:
            self._set_status("Connector endpoints must be different")
            return
        if any((tuple(c["a"]) == a and tuple(c["b"]) == b) or (tuple(c["a"]) == b and tuple(c["b"]) == a) for c in self.connectors):
            self._pending_connector = None
            self._set_status("Connector already exists")
            self.redraw()
            return
        self._push_undo()
        conn = self._build_connector(a, b)
        self.connectors.append(conn)
        self._pending_connector = None
        self.build_graph()
        self.redraw()
        if conn["kind"] == "interchange":
            self._set_status(f"Interchange added ({conn['level_span']})")
        else:
            self._set_status(f"Connector added L{a[2]} <-> L{b[2]}")

    def _iter_road_segments(self):
        for r in self.roads.values():
            for i in range(len(r.geom) - 1):
                ax, ay = r.geom[i]
                bx, by = r.geom[i + 1]
                yield r, ax, ay, bx, by

    def _nearest_segment_projection(self, px, py):
        best = None
        best_d = float("inf")
        for r, ax, ay, bx, by in self._iter_road_segments():
            dx = bx - ax
            dy = by - ay
            denom = dx * dx + dy * dy
            if denom <= 0:
                continue
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
            sx = ax + t * dx
            sy = ay + t * dy
            d = math.hypot(px - sx, py - sy)
            if d < best_d:
                best_d = d
                best = (sx, sy, math.atan2(dy, dx), r, d)
        return best

    def _pick_drive_spawn(self):
        if len(self.route_path) > 1:
            a = self.route_path[0]
            b = self.route_path[1]
            return (a[0], a[1], math.atan2(b[1] - a[1], b[0] - a[0]))
        if self.selected and len(self.selected.geom) > 1:
            a = self.selected.geom[0]
            b = self.selected.geom[1]
            return (a[0], a[1], math.atan2(b[1] - a[1], b[0] - a[0]))
        for r in self.roads.values():
            if len(r.geom) > 1:
                a = r.geom[0]
                b = r.geom[1]
                return (a[0], a[1], math.atan2(b[1] - a[1], b[0] - a[0]))
        return None

    def _lerp_angle(self, a, b, t):
        diff = (b - a + math.pi) % (2 * math.pi) - math.pi
        return a + diff * max(0.0, min(1.0, t))

    def _drive_key_press(self, e):
        mapping = {"Up": "w", "Down": "s", "Left": "a", "Right": "d"}
        key = mapping.get(e.keysym, e.keysym.lower())
        if key in {"w", "a", "s", "d"}:
            self._drive_keys.add(key)

    def _drive_key_release(self, e):
        mapping = {"Up": "w", "Down": "s", "Left": "a", "Right": "d"}
        key = mapping.get(e.keysym, e.keysym.lower())
        if key in self._drive_keys:
            self._drive_keys.remove(key)

    def open_drive_mode(self):
        if not self.roads:
            self._set_status("Drive mode unavailable: draw at least one road first")
            return
        if self._drive_win and self._drive_win.winfo_exists():
            self._drive_win.deiconify()
            self._drive_win.lift()
            self._drive_win.focus_force()
            return
        spawn = self._pick_drive_spawn()
        if not spawn:
            self._set_status("Drive mode unavailable: no drivable segment found")
            return
        self._drive_pos = (spawn[0], spawn[1])
        self._drive_heading = spawn[2]
        self._drive_speed = 0.0
        self._drive_keys = set()

        win = tk.Toplevel(self.root)
        win.title(f"{APP_TITLE} - 3D Drive")
        win.geometry("980x620")
        win.configure(bg="#0a0d15")
        win.minsize(700, 440)
        win.bind("<KeyPress>", self._drive_key_press)
        win.bind("<KeyRelease>", self._drive_key_release)
        win.bind("<Escape>", lambda _e: self.close_drive_mode())
        win.protocol("WM_DELETE_WINDOW", self.close_drive_mode)

        hud = tk.Label(
            win,
            text="WASD / Arrow Keys: Drive   |   Esc: Exit",
            bg="#0a0d15",
            fg="#98a8c8",
            font=("Consolas", 10, "bold"),
            pady=8,
        )
        hud.pack(side="top", fill="x")

        self._drive_canvas = tk.Canvas(win, bg="#070a12", highlightthickness=0, bd=0)
        self._drive_canvas.pack(side="top", fill="both", expand=True)

        self._drive_win = win
        self._drive_last_tick = time.perf_counter()
        self._set_status("3D drive mode active")
        win.focus_force()
        self._drive_tick()

    def close_drive_mode(self):
        if self._drive_after_id and self._drive_win and self._drive_win.winfo_exists():
            try:
                self._drive_win.after_cancel(self._drive_after_id)
            except tk.TclError:
                pass
        self._drive_after_id = None
        self._drive_last_tick = None
        self._drive_keys = set()
        if self._drive_win and self._drive_win.winfo_exists():
            try:
                self._drive_win.destroy()
            except tk.TclError:
                pass
        self._drive_win = None
        self._drive_canvas = None
        self._set_status("3D drive mode closed")

    def _drive_tick(self):
        if not (self._drive_win and self._drive_win.winfo_exists() and self._drive_canvas):
            self._drive_after_id = None
            return
        now = time.perf_counter()
        if self._drive_last_tick is None:
            dt = 1 / 60
        else:
            dt = max(0.005, min(0.05, now - self._drive_last_tick))
        self._drive_last_tick = now

        throttle = (1 if "w" in self._drive_keys else 0) - (1 if "s" in self._drive_keys else 0)
        steer = (1 if "d" in self._drive_keys else 0) - (1 if "a" in self._drive_keys else 0)

        if throttle > 0:
            self._drive_speed += DRIVE_ACCEL * dt
        elif throttle < 0:
            self._drive_speed -= DRIVE_BRAKE * dt
        else:
            self._drive_speed *= max(0.0, 1.0 - 1.3 * dt)

        self._drive_speed = max(-DRIVE_REVERSE_SPEED, min(DRIVE_MAX_SPEED, self._drive_speed))
        turn_gain = max(0.18, min(1.0, abs(self._drive_speed) / DRIVE_MAX_SPEED))
        self._drive_heading += steer * DRIVE_TURN_RATE * dt * turn_gain * (1 if self._drive_speed >= 0 else -1)

        x, y = self._drive_pos
        nx = x + math.cos(self._drive_heading) * self._drive_speed * dt
        ny = y + math.sin(self._drive_heading) * self._drive_speed * dt

        nearest = self._nearest_segment_projection(nx, ny)
        if nearest:
            sx, sy, seg_heading, _road, dist = nearest
            if dist <= DRIVE_LOCK_DIST:
                snap = min(1.0, dt * (8.0 - 6.0 * (dist / max(DRIVE_LOCK_DIST, 1.0))))
                nx = nx + (sx - nx) * snap
                ny = ny + (sy - ny) * snap
                align = min(1.0, dt * 2.5)
                self._drive_heading = self._lerp_angle(self._drive_heading, seg_heading, align)
                if dist > DRIVE_LOCK_DIST * 0.6:
                    self._drive_speed *= 0.97
            elif dist > DRIVE_HARD_LIMIT_DIST:
                self._drive_speed *= 0.78

        self._drive_pos = (nx, ny)
        self._draw_drive_scene(nearest)
        self._drive_after_id = self._drive_win.after(16, self._drive_tick)

    def _draw_drive_scene(self, nearest):
        c = self._drive_canvas
        w = c.winfo_width() or 980
        h = c.winfo_height() or 620
        c.delete("all")

        horizon = h * 0.44
        c.create_rectangle(0, 0, w, horizon, fill="#121a2c", outline="")
        c.create_rectangle(0, horizon, w, h, fill="#1b1a18", outline="")

        if self._drive_pos is None:
            return

        px, py = self._drive_pos
        heading = self._drive_heading
        cos_h = math.cos(heading)
        sin_h = math.sin(heading)
        near_plane = 4.0
        lane_width = 10.0
        seg_draw = []

        for road, ax, ay, bx, by in self._iter_road_segments():
            dax = ax - px
            day = ay - py
            dbx = bx - px
            dby = by - py
            za = cos_h * dax + sin_h * day
            xa = -sin_h * dax + cos_h * day
            zb = cos_h * dbx + sin_h * dby
            xb = -sin_h * dbx + cos_h * dby
            if za <= near_plane and zb <= near_plane:
                continue
            if za <= near_plane or zb <= near_plane:
                t = (near_plane - za) / (zb - za)
                if za < near_plane:
                    za = near_plane
                    xa = xa + t * (xb - xa)
                else:
                    zb = near_plane
                    xb = xb + t * (xa - xb)

            def proj(xc, zc):
                scale = 760.0 / (zc + 70.0)
                sx = w * 0.5 + xc * scale
                sy = horizon + 255.0 / (zc + 45.0)
                return sx, sy, scale

            l1x, l1y, _ = proj(xa - lane_width, za)
            r1x, r1y, _ = proj(xa + lane_width, za)
            l2x, l2y, _ = proj(xb - lane_width, zb)
            r2x, r2y, _ = proj(xb + lane_width, zb)
            depth = min(za, zb)
            seg_draw.append((depth, road, l1x, l1y, r1x, r1y, l2x, l2y, r2x, r2y))

        seg_draw.sort(key=lambda it: it[0], reverse=True)
        for _depth, road, l1x, l1y, r1x, r1y, l2x, l2y, r2x, r2y in seg_draw:
            road_col = ROAD_STYLES.get(road.rtype, {}).get("color", "#777")
            c.create_polygon(l1x, l1y, r1x, r1y, r2x, r2y, l2x, l2y, fill="#2d2a27", outline="")
            c.create_line(l1x, l1y, l2x, l2y, fill=road_col, width=2)
            c.create_line(r1x, r1y, r2x, r2y, fill=road_col, width=2)

        cx = w * 0.5
        base_y = h - 72
        c.create_polygon(
            cx - 30, base_y,
            cx + 30, base_y,
            cx + 22, base_y - 42,
            cx - 22, base_y - 42,
            fill="#d91010",
            outline="#ffaeae",
            width=2,
        )
        c.create_rectangle(cx - 12, base_y - 34, cx + 12, base_y - 20, fill="#8a0000", outline="")

        speed_kmh = max(0.0, self._drive_speed * 0.9)
        c.create_text(14, 14, anchor="nw", fill="#dce7ff", font=("Consolas", 11, "bold"),
                      text=f"Speed: {speed_kmh:5.1f} km/h")
        c.create_text(14, 34, anchor="nw", fill="#9db0d8", font=("Consolas", 10),
                      text="Controls: W/S throttle, A/D steer, Arrow keys supported")
        if nearest:
            _sx, _sy, _ang, road, dist = nearest
            c.create_text(14, 54, anchor="nw", fill="#9db0d8", font=("Consolas", 10),
                          text=f"Road: {road.name or 'Unnamed'} | L{int(road.bridge_level)} | offset {dist:.1f}")

    def apply(self):
        if not self.selected:
            return
        self._push_undo()
        r = self.selected
        old_level = int(r.bridge_level)
        old_pts = {tuple(pt) for pt in r.geom}
        r.name    = self._name_var.get().strip() or "Unnamed"
        r.ref     = self._ref_var.get().strip()
        r.rtype   = self._type_var.get()
        r.surface = self._surface_var.get()
        r.oneway  = bool(self._oneway_var.get())
        r.tunnel  = bool(self._tunnel_var.get())
        r.lit     = bool(self._lit_var.get())
        try:
            r.speed = int(self._speed_var.get())
        except ValueError:
            pass
        try:
            r.lanes = int(self._lanes_var.get())
        except ValueError:
            pass
        try:
            r.bridge_level = int(self._bridge_level_var.get())
        except ValueError:
            pass
        try:
            r.max_weight = float(self._max_weight_var.get())
        except ValueError:
            pass
        new_level = int(r.bridge_level)
        if new_level != old_level and old_pts:
            for conn in self.connectors:
                a = tuple(conn.get("a", []))
                b = tuple(conn.get("b", []))
                if len(a) == 3 and (a[0], a[1]) in old_pts and int(a[2]) == old_level:
                    conn["a"] = [a[0], a[1], new_level]
                if len(b) == 3 and (b[0], b[1]) in old_pts and int(b[2]) == old_level:
                    conn["b"] = [b[0], b[1], new_level]
        self.dirty = True
        self.build_graph()
        self._update_info(r)
        self.redraw()
        self._set_status(f"Changes applied to '{r.name}'")

    def load_fields(self, r):
        self._name_var.set(r.name)
        self._ref_var.set(r.ref)
        self._type_var.set(r.rtype)
        self._surface_var.set(r.surface)
        self._speed_var.set(str(r.speed))
        self._lanes_var.set(str(r.lanes))
        self._bridge_level_var.set(str(r.bridge_level))
        self._max_weight_var.set(str(r.max_weight) if r.max_weight else "")
        self._oneway_var.set(int(r.oneway))
        self._tunnel_var.set(int(r.tunnel))
        self._lit_var.set(int(r.lit))
        self._on_type_change()

    def _update_info(self, r):
        style = ROAD_STYLES.get(r.rtype, {})
        flags = []
        if r.oneway:
            flags.append("one-way")
        if r.tunnel:
            flags.append("tunnel")
        if r.lit:
            flags.append("lit")
        if r.bridge_level > 0:
            flags.append(f"bridge L{r.bridge_level}")
        flags_str  = "  ".join(flags) if flags else "none"
        weight_str = f"{r.max_weight}t" if r.max_weight else "unlimited"
        ref_str    = r.ref if r.ref else "-"
        self._info_var.set(
            f"FID:     {r.id[:10]}...\n"
            f"Ref:     {ref_str}\n"
            f"Class:   {style.get('label', r.rtype)}\n"
            f"Surface: {r.surface}\n"
            f"Speed:   {r.speed} km/h\n"
            f"Lanes:   {r.lanes}\n"
            f"Weight:  {weight_str}\n"
            f"Level:   {r.bridge_level}\n"
            f"Flags:   {flags_str}\n"
            f"Verts:   {len(r.geom)}\n"
            f"Length:  {r.length():.1f} units"
        )

    def delete_selected(self):
        if self.selected and self.selected.id in self.roads:
            self._push_undo()
            name = self.selected.name
            level = int(self.selected.bridge_level)
            pts = {tuple(pt) for pt in self.selected.geom}
            if pts:
                kept = []
                for conn in self.connectors:
                    try:
                        a = tuple(conn["a"])
                        b = tuple(conn["b"])
                    except Exception:
                        continue
                    a_hits = len(a) == 3 and (a[0], a[1]) in pts and int(a[2]) == level
                    b_hits = len(b) == 3 and (b[0], b[1]) in pts and int(b[2]) == level
                    if not (a_hits or b_hits):
                        kept.append(conn)
                self.connectors = kept
            del self.roads[self.selected.id]
            self.selected  = None
            self.drag_info = None
            self.dirty     = True
            self.build_graph()
            self._road_count_var.set(str(len(self.roads)))
            self._info_var.set("No feature selected")
            self.redraw()
            self._set_status(f"Deleted '{name}'  -  {len(self.roads)} remain")

    def clear_canvas(self):
        if messagebox.askyesno("Clear Layer", "Remove all features from this layer?"):
            self._push_undo()
            self.roads     = {}
            self.connectors = []
            self._pending_connector = None
            self.current   = []
            self.selected  = None
            self.graph     = {}
            self._clear_route()
            self.dirty     = True
            self._road_count_var.set("0")
            self._info_var.set("No feature selected")
            self.redraw()
            self._set_status("Layer cleared")

    def _default_plugin_manifests(self):
        if not os.path.isdir(PLUGIN_MANIFESTS_DIR):
            return []
        manifests = []
        for name in sorted(os.listdir(PLUGIN_MANIFESTS_DIR)):
            if name.lower().endswith(".json"):
                manifests.append(os.path.join(PLUGIN_MANIFESTS_DIR, name))
        return manifests

    def _normalize_plugin_entry(self, entry, default_enabled=False):
        if not isinstance(entry, dict):
            return None
        plugin_id = str(entry.get("id", "")).strip()
        name = str(entry.get("name", "")).strip()
        language = str(entry.get("language", "unknown")).strip().lower()
        description = str(entry.get("description", "")).strip()
        command = entry.get("command")
        hooks = entry.get("hooks", ["export_json"])
        timeout = entry.get("timeout", 6)
        enabled = bool(entry.get("enabled", default_enabled))
        if not plugin_id or not name:
            return None
        if not isinstance(command, list) or not command:
            return None
        command = [str(tok) for tok in command if str(tok).strip()]
        if not command:
            return None
        if not isinstance(hooks, list) or not hooks:
            hooks = ["export_json"]
        hooks = [str(h).strip() for h in hooks if str(h).strip()]
        if not hooks:
            hooks = ["export_json"]
        try:
            timeout = max(1, min(30, int(timeout)))
        except (TypeError, ValueError):
            timeout = 6
        return {
            "id": plugin_id,
            "name": name,
            "language": language,
            "description": description,
            "command": command,
            "hooks": hooks,
            "timeout": timeout,
            "enabled": enabled,
        }

    def _expand_command_tokens(self, command):
        expanded = []
        for tok in command:
            s = str(tok)
            s = s.replace("{{BASE_DIR}}", BASE_DIR)
            s = s.replace("{{POLYGLOT_DIR}}", POLYGLOT_DIR)
            s = s.replace("{{PLUGIN_DIR}}", PLUGIN_DIR)
            expanded.append(s)
        return expanded

    def _load_plugins_registry(self):
        os.makedirs(PLUGIN_DIR, exist_ok=True)
        plugins = []
        if os.path.exists(PLUGIN_REGISTRY_PATH):
            try:
                with open(PLUGIN_REGISTRY_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    for entry in loaded:
                        norm = self._normalize_plugin_entry(entry)
                        if norm:
                            plugins.append(norm)
            except (OSError, json.JSONDecodeError):
                plugins = []
        by_id = {p["id"]: p for p in plugins}
        for manifest_path in self._default_plugin_manifests():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            norm = self._normalize_plugin_entry(entry, default_enabled=False)
            if norm and norm["id"] not in by_id:
                by_id[norm["id"]] = norm
        self._plugins = sorted(by_id.values(), key=lambda p: (p["name"].lower(), p["id"]))
        self._save_plugins_registry()

    def _save_plugins_registry(self):
        os.makedirs(PLUGIN_DIR, exist_ok=True)
        try:
            with open(PLUGIN_REGISTRY_PATH, "w", encoding="utf-8") as f:
                json.dump(self._plugins, f, indent=2)
        except OSError:
            pass

    def _reload_plugins_registry(self):
        self._load_plugins_registry()
        self._refresh_plugin_manager_list()
        self._set_status(f"Plugin registry reloaded ({len(self._plugins)} plugins)")

    def install_builtin_plugins(self):
        installed = 0
        by_id = {p["id"] for p in self._plugins}
        for manifest_path in self._default_plugin_manifests():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            norm = self._normalize_plugin_entry(entry, default_enabled=False)
            if norm and norm["id"] not in by_id:
                self._plugins.append(norm)
                by_id.add(norm["id"])
                installed += 1
        self._plugins.sort(key=lambda p: (p["name"].lower(), p["id"]))
        self._save_plugins_registry()
        self._refresh_plugin_manager_list()
        self._set_status(f"Installed {installed} built-in plugins")

    def _selected_plugin_id(self):
        tree = getattr(self, "_plugin_tree", None)
        if not tree:
            return None
        sel = tree.selection()
        if not sel:
            return None
        values = tree.item(sel[0], "values")
        if not values:
            return None
        return values[0]

    def _refresh_plugin_manager_list(self):
        tree = getattr(self, "_plugin_tree", None)
        if not tree:
            return
        tree.delete(*tree.get_children())
        for plugin in self._plugins:
            hooks = ",".join(plugin.get("hooks", []))
            tree.insert(
                "",
                "end",
                values=(
                    plugin["id"],
                    "Yes" if plugin.get("enabled") else "No",
                    plugin.get("name", ""),
                    plugin.get("language", ""),
                    hooks,
                    plugin.get("timeout", 6),
                ),
            )

    def _install_plugin_manifest(self, manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                entry = json.load(f)
        except (OSError, json.JSONDecodeError) as ex:
            messagebox.showerror("Plugin Install Error", f"Failed to read manifest:\n{ex}")
            return
        norm = self._normalize_plugin_entry(entry, default_enabled=True)
        if not norm:
            messagebox.showerror("Plugin Install Error", "Manifest is missing required fields.")
            return
        for i, plugin in enumerate(self._plugins):
            if plugin["id"] == norm["id"]:
                self._plugins[i] = norm
                self._save_plugins_registry()
                self._refresh_plugin_manager_list()
                self._set_status(f"Plugin updated: {norm['name']}")
                return
        self._plugins.append(norm)
        self._plugins.sort(key=lambda p: (p["name"].lower(), p["id"]))
        self._save_plugins_registry()
        self._refresh_plugin_manager_list()
        self._set_status(f"Plugin installed: {norm['name']}")

    def install_plugin_from_manifest_dialog(self):
        path = filedialog.askopenfilename(
            title="Install Plugin Manifest",
            filetypes=[("Plugin Manifest", "*.json"), ("All Files", "*.*")],
        )
        if path:
            self._install_plugin_manifest(path)

    def _toggle_selected_plugin(self):
        plugin_id = self._selected_plugin_id()
        if not plugin_id:
            return
        for plugin in self._plugins:
            if plugin["id"] == plugin_id:
                plugin["enabled"] = not plugin.get("enabled", False)
                state = "enabled" if plugin["enabled"] else "disabled"
                self._set_status(f"Plugin {state}: {plugin['name']}")
                break
        self._save_plugins_registry()
        self._refresh_plugin_manager_list()

    def _remove_selected_plugin(self):
        plugin_id = self._selected_plugin_id()
        if not plugin_id:
            return
        for plugin in self._plugins:
            if plugin["id"] == plugin_id:
                if not messagebox.askyesno("Remove Plugin", f"Remove plugin '{plugin['name']}' from registry?"):
                    return
                break
        self._plugins = [p for p in self._plugins if p["id"] != plugin_id]
        self._save_plugins_registry()
        self._refresh_plugin_manager_list()
        self._set_status(f"Plugin removed: {plugin_id}")

    def open_plugin_manager(self):
        if self._plugin_manager_win and self._plugin_manager_win.winfo_exists():
            self._plugin_manager_win.lift()
            self._plugin_manager_win.focus_force()
            return
        win = tk.Toplevel(self.root)
        win.title(f"{APP_TITLE} - Plugin Manager")
        win.geometry("960x520")
        win.configure(bg=DARK_BG)
        win.minsize(760, 420)
        self._plugin_manager_win = win

        top = tk.Frame(win, bg=PANEL_BG, highlightthickness=1, highlightbackground=BORDER)
        top.pack(fill="both", expand=True, padx=10, pady=10)

        cols = ("id", "enabled", "name", "language", "hooks", "timeout")
        tree = ttk.Treeview(top, columns=cols, show="headings", height=14)
        self._plugin_tree = tree
        tree.heading("id", text="ID")
        tree.heading("enabled", text="Enabled")
        tree.heading("name", text="Name")
        tree.heading("language", text="Language")
        tree.heading("hooks", text="Hooks")
        tree.heading("timeout", text="Timeout(s)")
        tree.column("id", width=170, anchor="w")
        tree.column("enabled", width=70, anchor="center")
        tree.column("name", width=180, anchor="w")
        tree.column("language", width=90, anchor="center")
        tree.column("hooks", width=180, anchor="w")
        tree.column("timeout", width=90, anchor="center")
        tree.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 4))

        btns = tk.Frame(top, bg=PANEL_BG)
        btns.pack(side="top", fill="x", padx=8, pady=(4, 8))
        for text, cmd, color in [
            ("Install Manifest", self.install_plugin_from_manifest_dialog, ACCENT),
            ("Install Built-ins", self.install_builtin_plugins, "#3d9b7a"),
            ("Enable / Disable", self._toggle_selected_plugin, "#7b88b3"),
            ("Remove", self._remove_selected_plugin, ACCENT2),
            ("Reload", self._reload_plugins_registry, "#5776b2"),
            ("Run on Current Layer", self.run_plugins_on_current_layer, "#c08f3f"),
        ]:
            tk.Button(
                btns, text=text, command=cmd,
                bg=color, fg="white", relief="flat", bd=0,
                font=("Consolas", 9, "bold"), padx=10, pady=5, cursor="hand2",
            ).pack(side="left", padx=4)
        self._refresh_plugin_manager_list()

    def _run_plugin_process(self, plugin, payload):
        cmd = self._expand_command_tokens(plugin.get("command", []))
        timeout = plugin.get("timeout", 6)
        out = self._run_json_process(cmd, payload, timeout=timeout)
        if isinstance(out, dict):
            out.setdefault("plugin_id", plugin.get("id"))
            out.setdefault("plugin_name", plugin.get("name"))
            out.setdefault("engine", plugin.get("language", "unknown"))
        return out

    def _run_plugins_for_hook(self, hook, payload):
        outputs = []
        errors = []
        for plugin in self._plugins:
            if not plugin.get("enabled", False):
                continue
            hooks = plugin.get("hooks", [])
            if hook not in hooks:
                continue
            result = self._run_plugin_process(plugin, payload)
            if isinstance(result, dict):
                outputs.append(result)
            else:
                errors.append({
                    "plugin_id": plugin.get("id"),
                    "plugin_name": plugin.get("name"),
                    "error": "Plugin execution failed",
                })
        return outputs, errors

    def run_plugins_on_current_layer(self):
        payload = {
            "roads": [r.to_dict() for r in self.roads.values()],
            "connectors": self.connectors,
            "feature_count": len(self.roads),
        }
        outputs, errors = self._run_plugins_for_hook("manual", payload)
        summary = [f"Plugins run: {len(outputs)} succeeded"]
        if errors:
            summary.append(f"{len(errors)} failed")
        if outputs:
            names = ", ".join(o.get("plugin_name", o.get("plugin_id", "?")) for o in outputs[:6])
            summary.append(f"OK: {names}")
        if errors:
            names = ", ".join(e.get("plugin_name", e.get("plugin_id", "?")) for e in errors[:6])
            summary.append(f"Failed: {names}")
        messagebox.showinfo("Plugin Run Result", "\n".join(summary))
        self._set_status("Plugins executed on current layer")

    def _payload_validation_issues(self, payload):
        issues = []
        if not isinstance(payload, dict):
            return ["Payload is not an object"]
        roads = payload.get("roads")
        connectors = payload.get("connectors", [])
        if not isinstance(roads, list):
            issues.append("'roads' must be an array")
            roads = []
        if not isinstance(connectors, list):
            issues.append("'connectors' must be an array")
            connectors = []
        for idx, road in enumerate(roads):
            if not isinstance(road, dict):
                issues.append(f"road[{idx}] is not an object")
                continue
            if "name" not in road:
                issues.append(f"road[{idx}] missing 'name'")
            geom = road.get("geom")
            if not isinstance(geom, list) or len(geom) < 2:
                issues.append(f"road[{idx}] has invalid geometry")
                continue
            for j, pt in enumerate(geom):
                if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                    issues.append(f"road[{idx}].geom[{j}] invalid point")
                    break
        for idx, conn in enumerate(connectors):
            if not isinstance(conn, dict):
                issues.append(f"connector[{idx}] is not an object")
                continue
            for side in ("a", "b"):
                node = conn.get(side)
                if not isinstance(node, (list, tuple)) or len(node) != 3:
                    issues.append(f"connector[{idx}].{side} must be [x,y,level]")
        return issues

    def _validate_payload_polyglot(self, payload):
        validators = []
        if os.path.exists(RUST_VALIDATOR_MANIFEST) and shutil.which("cargo"):
            validators.append(("rust-validator", ["cargo", "run", "--quiet", "--release", "--manifest-path", RUST_VALIDATOR_MANIFEST], 20))
        if os.path.exists(GO_VALIDATOR_SCRIPT) and shutil.which("go"):
            validators.append(("go-validator", ["go", "run", GO_VALIDATOR_SCRIPT], 12))
        for engine, cmd, timeout in validators:
            out = self._run_json_process(cmd, payload, timeout=timeout)
            if isinstance(out, dict):
                out.setdefault("engine", engine)
                if isinstance(out.get("issues"), list):
                    return out
        return None

    def validate_layer_file_dialog(self):
        path = filedialog.askopenfilename(
            title="Validate Layer File",
            filetypes=[
                ("RoadGIS Layer", f"*{FILE_EXT}"),
                ("JSON", "*.json"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        issues = []
        payload = None
        try:
            with open(path, "rb") as f:
                raw = f.read()
            if os.path.splitext(path)[1].lower() == ".json":
                payload = json.loads(raw.decode("utf-8"))
                if isinstance(payload, list):
                    payload = {"roads": payload, "connectors": []}
            else:
                payload = decode_rgis(raw)
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, struct.error) as ex:
            messagebox.showerror("Validation Error", f"File decode failed:\n{ex}")
            return
        issues.extend(self._payload_validation_issues(payload))
        poly_out = self._validate_payload_polyglot(payload)
        if poly_out and isinstance(poly_out.get("issues"), list):
            for issue in poly_out["issues"]:
                if isinstance(issue, str) and issue not in issues:
                    issues.append(issue)
        if issues:
            preview = "\n".join(f"- {msg}" for msg in issues[:24])
            if len(issues) > 24:
                preview += f"\n... and {len(issues) - 24} more"
            messagebox.showwarning("Validation Result", f"Found {len(issues)} issue(s):\n{preview}")
            self._set_status(f"Validation found {len(issues)} issue(s)")
        else:
            messagebox.showinfo("Validation Result", "File is valid.")
            self._set_status("Validation passed")

    def save(self):
        if not self.file:
            return self.save_as()
        return self._write_file(self.file)

    def save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=FILE_EXT,
            filetypes=[("RoadGIS Layer", f"*{FILE_EXT}"), ("All Files", "*.*")],
            title="Save Layer",
        )
        if path:
            self.file = path
            return self._write_file(path)
        return False

    def _write_file(self, path):
        tmp_path = f"{path}.tmp"
        try:
            data = {
                "roads": [r.to_dict() for r in self.roads.values()],
                "connectors": self.connectors,
            }
            encoded = encode_rgis(data)
            with open(tmp_path, "wb") as f:
                f.write(encoded)
            os.replace(tmp_path, path)
            self.dirty = False
            self._set_status(f"Saved  {path}")
            self.root.title(f"{APP_TITLE}  -  {path}")
            return True
        except OSError as ex:
            messagebox.showerror("Save Error", str(ex))
            return False
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Export Layer as Plain JSON",
        )
        if not path:
            return
        try:
            payload = {
                "roads": [r.to_dict() for r in self.roads.values()],
                "connectors": self.connectors,
            }
            metrics = self._compute_metrics_polyglot(payload)
            plugin_payload = {
                "roads": payload["roads"],
                "connectors": payload["connectors"],
                "feature_count": len(self.roads),
                "metrics": metrics,
            }
            plugin_outputs, plugin_errors = self._run_plugins_for_hook("export_json", plugin_payload)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "roads":         payload["roads"],
                    "connectors":    payload["connectors"],
                    "feature_count": len(self.roads),
                    "graph_nodes":   len(self.graph),
                    "metrics":       metrics,
                    "plugin_outputs": plugin_outputs,
                    "plugin_errors": plugin_errors,
                }, f, indent=2)
            self._set_status(f"Exported to {path}")
        except OSError as ex:
            messagebox.showerror("Export Error", str(ex))

    def _compute_metrics_fallback(self, payload):
        roads = payload.get("roads", [])
        if not isinstance(roads, list):
            roads = []
        connectors = payload.get("connectors", [])
        if not isinstance(connectors, list):
            connectors = []
        road_count = len(roads)
        total_len = 0.0
        total_speed = 0.0
        total_lanes = 0
        oneway_count = 0
        for r in roads:
            if not isinstance(r, dict):
                continue
            try:
                total_speed += float(r.get("speed", 0.0) or 0.0)
            except (TypeError, ValueError):
                pass
            try:
                total_lanes += int(float(r.get("lanes", 0) or 0))
            except (TypeError, ValueError):
                pass
            if as_bool(r.get("oneway", False)):
                oneway_count += 1
            geom = r.get("geom", [])
            if not isinstance(geom, list):
                continue
            for i in range(len(geom) - 1):
                a = geom[i]
                b = geom[i + 1]
                if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)):
                    continue
                if len(a) < 2 or len(b) < 2:
                    continue
                try:
                    ax, ay = float(a[0]), float(a[1])
                    bx, by = float(b[0]), float(b[1])
                except (TypeError, ValueError):
                    continue
                total_len += math.hypot(bx - ax, by - ay)
        avg_speed = (total_speed / road_count) if road_count else 0.0
        avg_lanes = (total_lanes / road_count) if road_count else 0.0
        return {
            "engine": "python-fallback",
            "road_count": road_count,
            "connector_count": len(connectors),
            "total_length_km": total_len / 1000.0,
            "average_speed_limit": avg_speed,
            "average_lanes": avg_lanes,
            "oneway_share": (oneway_count / road_count) if road_count else 0.0,
        }

    def _compute_metrics_polyglot(self, payload):
        engines = []
        if os.path.exists(JS_METRICS_SCRIPT) and shutil.which("node"):
            engines.append(("javascript", ["node", JS_METRICS_SCRIPT], 8))
        if os.path.exists(GO_METRICS_SCRIPT) and shutil.which("go"):
            engines.append(("go", ["go", "run", GO_METRICS_SCRIPT], 10))
        if os.path.exists(CSHARP_METRICS_PROJECT) and shutil.which("dotnet"):
            engines.append(("csharp", ["dotnet", "run", "--project", CSHARP_METRICS_PROJECT, "-c", "Release"], 20))
        for engine_name, cmd, timeout in engines:
            out = self._run_json_process(cmd, payload, timeout=timeout)
            if isinstance(out, dict):
                out.setdefault("engine", engine_name)
                return out
        return self._compute_metrics_fallback(payload)

    def load(self):
        if not self._ask_save():
            return
        path = filedialog.askopenfilename(
            filetypes=[
                ("RoadGIS Layer", f"*{FILE_EXT}"),
                ("JSON (legacy)", "*.json"),
                ("All Files", "*.*"),
            ],
            title="Open Layer",
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
            if os.path.splitext(path)[1].lower() == ".json":
                payload = json.loads(raw.decode("utf-8"))
                if isinstance(payload, list):
                    payload = {"roads": payload, "connectors": []}
                if not isinstance(payload, dict) or "roads" not in payload:
                    raise ValueError("Expected a JSON array or object with 'roads' key.")
                if "connectors" not in payload or not isinstance(payload["connectors"], list):
                    payload["connectors"] = []
            else:
                payload = decode_rgis(raw)
            self.roads    = {}
            self.connectors = self._normalize_connectors(payload.get("connectors", []))
            self._pending_connector = None
            self.current  = []
            self.selected = None
            self._undo_stack.clear()
            self._redo_stack.clear()
            skipped = 0
            for d in payload["roads"]:
                try:
                    r = Road.from_dict(d)
                except (ValueError, TypeError):
                    skipped += 1
                    continue
                self.roads[r.id] = r
            self.file  = path
            self.dirty = False
            self.build_graph()
            self._road_count_var.set(str(len(self.roads)))
            self.root.title(f"{APP_TITLE}  -  {path}")
            if skipped:
                self._set_status(f"Loaded {len(self.roads)} features from {path}  |  Skipped {skipped} invalid")
            else:
                self._set_status(f"Loaded {len(self.roads)} features from {path}")
            self.zoom_fit()
        except (OSError, ValueError, KeyError, struct.error) as ex:
            messagebox.showerror("Load Error", str(ex))

    def new(self):
        if not self._ask_save():
            return
        self.roads     = {}
        self.connectors = []
        self._pending_connector = None
        self.current   = []
        self.selected  = None
        self.file      = None
        self.dirty     = False
        self.graph     = {}
        self._clear_route()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._clipboard = None
        self._road_count_var.set("0")
        self._info_var.set("No feature selected")
        self.root.title(APP_TITLE)
        self.redraw()
        self._set_status("New layer")

    def _ask_save(self):
        if self.dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved Changes",
                "Save changes before continuing?",
            )
            if choice is None:
                return False
            if choice:
                return self.save()
        return True

    def on_close(self):
        if self._ask_save():
            self.close_drive_mode()
            if self._plugin_manager_win and self._plugin_manager_win.winfo_exists():
                try:
                    self._plugin_manager_win.destroy()
                except tk.TclError:
                    pass
            self.root.destroy()

    def _set_status(self, msg):
        self._status_var.set(msg)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()

