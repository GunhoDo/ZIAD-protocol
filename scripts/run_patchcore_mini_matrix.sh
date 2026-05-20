#!/usr/bin/env bash
# Run a PatchCore-only mini matrix on MVTec AD/bottle.
# This is a fast, paper-ineligible bridge between smoke and full P0.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MATRIX_CONFIG="${1:-experiments/configs/patchcore_mini_matrix.yaml}"
if [ ! -f "$MATRIX_CONFIG" ]; then
  echo "ERROR: mini-matrix config not found: $MATRIX_CONFIG" >&2
  exit 1
fi

mapfile -t RUN_CONFIGS < <(python3 - "$MATRIX_CONFIG" <<'PY'
import json
import pathlib
import re
import sys

config_path = pathlib.Path(sys.argv[1])
try:
    import yaml
except ImportError as error:
    raise SystemExit("PyYAML is required for mini-matrix config parsing") from error
cfg = yaml.safe_load(config_path.read_text())
if not isinstance(cfg, dict):
    raise SystemExit(f"Config must be a mapping: {config_path}")

baseline = cfg.get("baseline", "PatchCore")
baseline_path = cfg.get("baseline_path", "external/patchcore-inspection")
dataset = cfg.get("dataset", "MVTec AD")
dataset_root = cfg.get("dataset_root", "data/mvtec_ad")
category = cfg.get("category", "bottle")
prevalence = cfg.get("prevalence", 0.05)
stream_cfg = cfg.get("stream") or {}
outputs = cfg.get("outputs") or {}
root = pathlib.Path(outputs.get("root", "results/latest/mini_matrix"))
stream_types = cfg.get("stream_types") or [cfg.get("stream_type", "iid")]
epsilons = cfg.get("contamination_epsilon") or [0]
root.mkdir(parents=True, exist_ok=True)
configs_dir = root / "configs"
configs_dir.mkdir(parents=True, exist_ok=True)

def slug(value):
    text = str(value)
    text = text.replace(".", "p").replace("-", "m")
    return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")

for stream_type in stream_types:
    for epsilon in epsilons:
        run_id = f"patchcore_{slug(category)}_{slug(stream_type)}_eps_{slug(epsilon)}"
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_cfg = {
            "baseline": baseline,
            "baseline_path": baseline_path,
            "dataset": dataset,
            "dataset_root": dataset_root,
            "category": category,
            "stream_type": stream_type,
            "prevalence": prevalence,
            "contamination_epsilon": epsilon,
            "stream": {
                "path": str(run_dir / "stream.json"),
                "seed": stream_cfg.get("seed", 0),
                "length": stream_cfg.get("length"),
                "burst_length": stream_cfg.get("burst_length", 1),
            },
            "outputs": {
                "scores_csv": str(run_dir / "scores.csv"),
                "latest_run": str(run_dir / "latest_run.json"),
                "manifest": str(run_dir / "manifest.json"),
            },
        }
        path = configs_dir / f"{run_id}.yaml"
        path.write_text(yaml.safe_dump(run_cfg, sort_keys=False), encoding="utf-8")
        print(path)
PY
)

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

python3 - "$MATRIX_CONFIG" <<'PY'
import csv
import json
import pathlib
import sys

try:
    import yaml
except ImportError as error:
    raise SystemExit("PyYAML is required for mini-matrix aggregation") from error
cfg = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text())
outputs = cfg.get("outputs") or {}
root = pathlib.Path(outputs.get("root", "results/latest/mini_matrix"))
aggregate_metrics = pathlib.Path(outputs.get("aggregate_metrics", root / "metrics_patchcore_bottle.csv"))
aggregate_manifest = pathlib.Path(outputs.get("aggregate_manifest", root / "manifest_patchcore_bottle.json"))
rows = []
for metrics_path in sorted(root.glob("patchcore_*/metrics.csv")):
    with metrics_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row = dict(row)
            row["run_dir"] = str(metrics_path.parent)
            rows.append(row)
if not rows:
    raise SystemExit(f"No measured mini-matrix metrics found under {root}")
fieldnames = list(rows[0].keys())
aggregate_metrics.parent.mkdir(parents=True, exist_ok=True)
with aggregate_metrics.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
manifest = {
    "status": "patchcore_mini_matrix_complete",
    "paper_allowed": False,
    "aggregate_metrics": str(aggregate_metrics),
    "run_count": len(rows),
    "runs": rows,
    "notes": "PatchCore-only MVTec AD/bottle mini-matrix. Useful for pipeline validation; not full P0 or paper gate.",
}
aggregate_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
print(aggregate_metrics)
print(aggregate_manifest)
PY

echo "RESULT: PatchCore mini-matrix complete (paper_allowed=false)."
