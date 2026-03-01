# RoadGIS Pro Polyglot Engines

This folder adds optional cross-platform engines:

- `rust_router`: fastest-route solver (Dijkstra) in Rust
- `js/metrics.js`: export analytics engine in JavaScript (Node.js)

## Why this exists

`RoadGISPro.py` still runs standalone, but when these engines are available it uses them automatically.

## Build Rust router

```powershell
cd "C:\Users\Aaranya\Desktop\Programming\Extra\App\App Making\RoadGISProNotInGithub\polyglot\rust_router"
cargo build --release
```

The app will use `target/release/rust_router(.exe)` once built.

## JavaScript metrics

Install Node.js, then no build step is required.  
The app invokes `polyglot/js/metrics.js` during JSON export.

## Runtime behavior

- Routing: Rust first, Python fallback
- Metrics: JavaScript first, Python fallback
