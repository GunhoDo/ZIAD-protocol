#!/usr/bin/env bash
# Run the RareCLIP MVTec full-category smoke sweep.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SWEEP_CONFIG="${1:-experiments/configs/mvtec_full_category_sweep_rareclip.yaml}"
if [ ! -f "$SWEEP_CONFIG" ]; then
  echo "ERROR: RareCLIP MVTec full-category sweep config not found: $SWEEP_CONFIG" >&2
  exit 1
fi

bash scripts/run_mvtec_full_category_sweep.sh "$SWEEP_CONFIG"
