# RoadGIS Pro Polyglot Engines

This folder adds optional cross-platform engines:

- `rust_router`: fastest-route solver (Dijkstra) in Rust
- `js/metrics.js`: export analytics engine in JavaScript (Node.js)
- `go/metrics.go`: export analytics engine in Go
- `csharp/`: export analytics engine in C# (.NET)
- `ruby/`: optional export analytics engine in Ruby
- `java/`: optional export analytics engine in Java source mode
- `plugins/`: installable plugin engines and manifests (Go + Rust samples)
- `validators/`: file-format validators (Go + Rust)
- `setup/`: cross-OS language selection setup scripts

## Why this exists

`RoadGISPro.py` still runs standalone, but when these engines are available it uses them automatically.

## Build Rust router

```powershell
cd "[Insert Path]\YourRoadGISPath\polyglot\rust_router"
cargo build --release
```

The app will use `target/release/rust_router(.exe)` once built.

## JavaScript metrics

Install Node.js, then no build step is required.  
The app invokes `polyglot/js/metrics.js` during JSON export.

## Go metrics

Install Go, then no build step is required.  
The app can invoke `go run polyglot/go/metrics.go` during JSON export.

## C# metrics

Install .NET SDK 8+, then no manual build step is required.  
The app can invoke `dotnet run --project polyglot/csharp/MetricsEngine.csproj -c Release`.

## Runtime behavior

- Routing: Rust first, Python fallback
- Metrics: JavaScript, then Go, then C#, then Python fallback
- Optional Metrics: Ruby, Java (disabled by default in runtime config)
- Plugins: enabled plugins run on `export_json` and manual runs
- Validation: Rust validator, then Go validator, then Python checks

## Cross-OS setup

Generate `runtime_config.json` with selected languages/features:

Windows PowerShell:

```powershell
.\polyglot\setup\setup_languages.ps1 -Languages "rust_router,js_metrics,go_metrics,csharp_metrics,rust_validator,go_validator,plugins"
```

Linux/macOS:

```bash
./polyglot/setup/setup_languages.sh "rust_router,js_metrics,go_metrics,csharp_metrics,rust_validator,go_validator,plugins"
```

Direct Python:

```bash
python polyglot/setup/setup_languages.py --languages "rust_router,js_metrics,go_metrics,csharp_metrics,rust_validator,go_validator,plugins" --write-config polyglot/runtime_config.json
```

You can also start from `polyglot/runtime_config.example.json`.

Tokens available:

- `rust_router`
- `js_metrics`
- `go_metrics`
- `csharp_metrics`
- `ruby_metrics`
- `java_metrics`
- `rust_validator`
- `go_validator`
- `plugins`

## Plugin Manager (QGIS-style workflow)

Inside the app:

- Open `Plugins > Plugin Manager`
- Install from `*.json` manifest, or click `Install Built-ins`
- Enable/Disable or Remove plugins
- Run plugins manually on current layer

Manifest fields:

- `id`, `name`, `language`, `description`
- `command` (array of executable tokens)
- `hooks` (for example `["export_json", "manual"]`)
- `timeout` (seconds)

Token placeholders supported in commands:

- `{{BASE_DIR}}`
- `{{POLYGLOT_DIR}}`
- `{{PLUGIN_DIR}}`
