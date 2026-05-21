#!/usr/bin/env bash
# Run the WinCLIP MVTec all-category stream/epsilon smoke matrix.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SWEEP_CONFIG="${1:-experiments/configs/mvtec_full_category_stream_matrix_winclip.yaml}"
if [ ! -f "$SWEEP_CONFIG" ]; then
  echo "ERROR: WinCLIP MVTec full-category stream matrix config not found: $SWEEP_CONFIG" >&2
  exit 1
fi

bash scripts/run_mvtec_full_category_sweep.sh "$SWEEP_CONFIG"
