#!/usr/bin/env bash
# Run a small multi-category smoke sweep via the baseline mini-matrix runner.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SWEEP_CONFIG="${1:-experiments/configs/category_quick_sweep.yaml}"
if [ ! -f "$SWEEP_CONFIG" ]; then
  echo "ERROR: category quick-sweep config not found: $SWEEP_CONFIG" >&2
  exit 1
fi

mapfile -t MATRIX_CONFIGS < <(python3 experiments/category_sweep.py prepare "$SWEEP_CONFIG")

if [ "${#MATRIX_CONFIGS[@]}" -eq 0 ]; then
  echo "ERROR: category quick sweep produced no matrix configs" >&2
  exit 1
fi

for cfg in "${MATRIX_CONFIGS[@]}"; do
  echo "=== Category quick-sweep matrix: $cfg ==="
  bash scripts/run_baseline_mini_matrix.sh "$cfg"
done

python3 experiments/category_sweep.py aggregate "$SWEEP_CONFIG"

echo "RESULT: category quick sweep complete (paper_allowed=false)."
