#!/usr/bin/env bash
# Compatibility wrapper for the generic baseline mini-matrix runner.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash scripts/run_baseline_mini_matrix.sh "${1:-experiments/configs/patchcore_mini_matrix.yaml}"
