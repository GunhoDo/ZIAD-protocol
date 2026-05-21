#!/usr/bin/env bash
# Run the VisA full-category WinCLIP iid epsilon-zero smoke sweep.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

bash scripts/run_category_quick_sweep.sh experiments/configs/visa_full_category_sweep_winclip.yaml
