#!/usr/bin/env bash
# Run the configured MVTec full-category smoke sweep.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SWEEP_CONFIG="${1:-experiments/configs/mvtec_full_category_sweep_winclip.yaml}"
if [ ! -f "$SWEEP_CONFIG" ]; then
  echo "ERROR: MVTec full-category sweep config not found: $SWEEP_CONFIG" >&2
  exit 1
fi

mapfile -t MATRIX_CONFIGS < <(python3 experiments/category_sweep.py prepare "$SWEEP_CONFIG")

if [ "${#MATRIX_CONFIGS[@]}" -eq 0 ]; then
  echo "ERROR: MVTec full-category sweep produced no matrix configs" >&2
  exit 1
fi

for cfg in "${MATRIX_CONFIGS[@]}"; do
  echo "=== MVTec full-category sweep matrix: $cfg ==="
  bash scripts/run_baseline_mini_matrix.sh "$cfg"
done

python3 experiments/category_sweep.py aggregate "$SWEEP_CONFIG"

echo "RESULT: MVTec full-category sweep complete (paper_allowed=false)."
