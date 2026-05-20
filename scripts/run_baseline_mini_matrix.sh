#!/usr/bin/env bash
# Run a baseline mini-matrix on one dataset/category.
# This is a fast, paper-ineligible bridge between smoke and full P0.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MATRIX_CONFIG="${1:-experiments/configs/patchcore_mini_matrix.yaml}"
if [ ! -f "$MATRIX_CONFIG" ]; then
  echo "ERROR: mini-matrix config not found: $MATRIX_CONFIG" >&2
  exit 1
fi

mapfile -t RUN_CONFIGS < <(python3 experiments/mini_matrix.py prepare "$MATRIX_CONFIG")

if [ "${#RUN_CONFIGS[@]}" -eq 0 ]; then
  echo "ERROR: mini-matrix produced no run configs" >&2
  exit 1
fi

for cfg in "${RUN_CONFIGS[@]}"; do
  run_dir="$(dirname "$(dirname "$cfg")")/$(basename "$cfg" .yaml)"
  echo "=== Mini-matrix run: $cfg ==="
  bash scripts/run_smoke.sh "$cfg"
  python3 experiments/evaluate.py \
    --scores-csv "$run_dir/scores.csv" \
    --latest-run "$run_dir/latest_run.json" \
    --output "$run_dir/metrics.csv" \
    --manifest "$run_dir/manifest.json"
done

python3 experiments/mini_matrix.py aggregate "$MATRIX_CONFIG"

echo "RESULT: baseline mini-matrix complete (paper_allowed=false)."
