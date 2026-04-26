#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${SCRIPT_DIR}/out"
WORK_DIR="${SCRIPT_DIR}/work"

mkdir -p "${OUT_DIR}" "${WORK_DIR}"

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "RoadGISPro" \
  --distpath "${OUT_DIR}" \
  --workpath "${WORK_DIR}" \
  --add-data "${REPO_ROOT}/polyglot:polyglot" \
  --add-data "${REPO_ROOT}/roadgis_support:roadgis_support" \
  "${REPO_ROOT}/RoadGISPro.py"

echo "Built RoadGISPro ${VERSION} into ${OUT_DIR}"
