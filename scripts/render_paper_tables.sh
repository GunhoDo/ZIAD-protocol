#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$#" -gt 0 ]]; then
  python3 experiments/render_paper_tables.py "$@"
  exit 0
fi

python3 experiments/render_paper_tables.py

for baseline in winclip anomalyclip rareclip patchcore; do
  pretty="$baseline"
  case "$baseline" in
    winclip) pretty="WinCLIP" ;;
    anomalyclip) pretty="AnomalyCLIP" ;;
    rareclip) pretty="RareCLIP" ;;
    patchcore) pretty="PatchCore" ;;
  esac
  python3 experiments/render_paper_tables.py \
    --metrics-csv "results/latest/visa_full_category_stream_matrix_${baseline}_temperature/metrics_visa_full_category_stream_matrix_${baseline}_temperature.csv" \
    --manifest "results/latest/visa_full_category_stream_matrix_${baseline}_temperature/manifest_visa_full_category_stream_matrix_${baseline}_temperature.json" \
    --output "results/latest/tables/visa_${baseline}_temperature_smoke.tex" \
    --caption "VisA ${pretty} stream/epsilon/calibration metrics" \
    --label "tab:visa-${baseline}-temperature-smoke"
done
