#!/usr/bin/env bash
set -euo pipefail

LANGUAGES="${1:-rust_router,js_metrics,go_metrics,csharp_metrics,rust_validator,go_validator,plugins}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${SCRIPT_DIR}/setup_languages.py"
CFG="$(cd "${SCRIPT_DIR}/.." && pwd)/runtime_config.json"

python3 "$PY" --languages "$LANGUAGES" --write-config "$CFG"
