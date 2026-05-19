#!/usr/bin/env bash
set -euo pipefail

# Minimal P0 placeholder pipeline. It documents and refreshes the latest result
# contract without fabricating measured numbers.
python3 experiments/prepare_data.py --output results/latest/metadata.json
python3 experiments/make_streams.py --placeholder-p0
python3 experiments/run_baselines.py
python3 experiments/evaluate.py

echo "P0 placeholder outputs refreshed under results/latest/."
echo "Status remains placeholder until real datasets/checkpoints are configured."
