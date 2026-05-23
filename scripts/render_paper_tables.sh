#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$#" -gt 0 ]]; then
  python3 experiments/render_paper_tables.py "$@"
  exit 0
fi

python3 experiments/render_paper_tables.py

for dataset in mvtec visa; do
  dataset_title="MVTec AD"
  if [[ "$dataset" == "visa" ]]; then
    dataset_title="VisA"
  fi
  for baseline in winclip anomalyclip rareclip patchcore; do
  pretty="$baseline"
  case "$baseline" in
    winclip) pretty="WinCLIP" ;;
    anomalyclip) pretty="AnomalyCLIP" ;;
    rareclip) pretty="RareCLIP" ;;
    patchcore) pretty="PatchCore" ;;
  esac
  python3 experiments/render_paper_tables.py \
    --metrics-csv "results/latest/${dataset}_full_category_stream_matrix_${baseline}_temperature/metrics_${dataset}_full_category_stream_matrix_${baseline}_temperature.csv" \
    --manifest "results/latest/${dataset}_full_category_stream_matrix_${baseline}_temperature/manifest_${dataset}_full_category_stream_matrix_${baseline}_temperature.json" \
    --output "results/latest/tables/${dataset}_${baseline}_temperature_smoke.tex" \
    --caption "${dataset_title} ${pretty} stream/epsilon/calibration metrics" \
    --label "tab:${dataset}-${baseline}-temperature-smoke"
  done
done
