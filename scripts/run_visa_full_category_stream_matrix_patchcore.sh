#!/usr/bin/env bash
# Run the PatchCore VisA all-category stream/epsilon smoke matrix.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SWEEP_CONFIG="${1:-experiments/configs/visa_full_category_stream_matrix_patchcore.yaml}"
if [ ! -f "$SWEEP_CONFIG" ]; then
  echo "ERROR: PatchCore VisA full-category stream matrix config not found: $SWEEP_CONFIG" >&2
  exit 1
fi

bash scripts/run_category_quick_sweep.sh "$SWEEP_CONFIG"
