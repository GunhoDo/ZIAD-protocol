#!/usr/bin/env bash
# Run the WinCLIP MVTec AD all-category stream/epsilon/calibration smoke matrix.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SOURCE_SWEEP_CONFIG="${SOURCE_SWEEP_CONFIG:-experiments/configs/mvtec_full_category_stream_matrix_winclip.yaml}"
SWEEP_CONFIG="${1:-experiments/configs/mvtec_full_category_stream_matrix_winclip_temperature.yaml}"
if [ ! -f "$SWEEP_CONFIG" ]; then
  echo "ERROR: WinCLIP MVTec full-category temperature matrix config not found: $SWEEP_CONFIG" >&2
  exit 1
fi
if [ ! -f "$SOURCE_SWEEP_CONFIG" ]; then
  echo "ERROR: WinCLIP MVTec source stream matrix config not found: $SOURCE_SWEEP_CONFIG" >&2
  exit 1
fi

python3 experiments/materialize_calibration_matrix.py \
  --source-sweep-config "$SOURCE_SWEEP_CONFIG" \
  --target-sweep-config "$SWEEP_CONFIG"
