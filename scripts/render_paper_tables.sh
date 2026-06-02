#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$#" -gt 0 ]]; then
  python3 experiments/render_paper_tables.py "$@"
  exit 0
fi

python3 experiments/summarize_p0_smoke.py
python3 experiments/p0_full_report.py
python3 experiments/render_paper_tables.py
python3 experiments/repair_crd_lite_seed_matching.py
python3 experiments/summarize_paper_candidate_baselines.py
python3 experiments/summarize_paper_candidate_baselines.py \
  --input-root results/latest/paper_candidate/visa \
  --baseline winclip:default_no_memory \
  --baseline anomalyclip:default_no_memory \
  --baseline rareclip:default_scs \
  --baseline patchcore:default_scs \
  --output-csv results/latest/paper_candidate/visa/baseline_comparison_none.csv \
  --output-json results/latest/paper_candidate/visa/baseline_comparison_none.json \
  --output-tex results/latest/tables/paper_candidate_visa_baseline_comparison_none.tex
python3 experiments/summarize_paper_candidate_all_datasets.py
python3 experiments/render_paper_candidate_analysis.py
python3 experiments/audit_paper_candidate_metrics.py
python3 experiments/summarize_paper_candidate_stream_epsilon.py
python3 experiments/summarize_focused_evaluation_ci.py
python3 experiments/summarize_paper_candidate_stream_epsilon.py \
  --input-root results/latest/paper_candidate/diagnostic_order_sensitivity \
  --auto-discover \
  --expected-epsilons 0,0.05,0.1,0.2 \
  --output-csv results/latest/paper_candidate/diagnostic_order_sensitivity/stream_epsilon_breakdown.csv \
  --output-json results/latest/paper_candidate/diagnostic_order_sensitivity/stream_epsilon_breakdown.json \
  --output-tex results/latest/tables/order_sensitive_toy_stream_epsilon_breakdown.tex
python3 experiments/summarize_focused_evaluation_ci.py \
  --input-root results/latest/paper_candidate/diagnostic_order_sensitivity \
  --output-json results/latest/paper_candidate/diagnostic_order_sensitivity/focused_evaluation_ci_summary.json \
  --output-tex results/latest/tables/order_sensitive_toy_ci_summary.tex
python3 experiments/summarize_strong_epsilon_diagnostic.py
python3 experiments/render_protocol_overview.py

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

python3 experiments/render_paper_tables.py --write-input-contract
