#!/usr/bin/env bash
# Run the AnomalyCLIP VisA all-category stream/epsilon/calibration smoke matrix.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SWEEP_CONFIG="${1:-experiments/configs/visa_full_category_stream_matrix_anomalyclip_temperature.yaml}"
if [ ! -f "$SWEEP_CONFIG" ]; then
  echo "ERROR: AnomalyCLIP VisA full-category temperature matrix config not found: $SWEEP_CONFIG" >&2
  exit 1
fi

bash scripts/run_category_quick_sweep.sh "$SWEEP_CONFIG"
