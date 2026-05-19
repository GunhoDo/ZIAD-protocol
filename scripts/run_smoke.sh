#!/usr/bin/env bash
# Smoke run: one baseline + one dataset category -> results/latest/scores.csv
#
# Gates:
#   Setup smoke gate: exits with explicit error if baseline/data missing.
#                     Writes setup_incomplete status. Does NOT fabricate scores.
#   First success gate A: requires configured baseline + real data + stream file.
#
# Usage: bash scripts/run_smoke.sh [path/to/smoke.yaml]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CONFIG_FILE="${1:-experiments/configs/smoke.yaml}"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: Smoke config not found: $CONFIG_FILE" >&2
  exit 1
fi

# Parse config fields with python (avoids yq dependency)
read -r SMOKE_BASELINE SMOKE_BASELINE_PATH SMOKE_DATASET_ROOT SMOKE_CATEGORY SMOKE_STREAM_TYPE SMOKE_STREAM_PATH < <(python3 - "$CONFIG_FILE" <<'PY'
import sys, pathlib

cfg_text = pathlib.Path(sys.argv[1]).read_text()
try:
    import yaml
    cfg = yaml.safe_load(cfg_text)
except ImportError:
    # Minimal key=value fallback without PyYAML
    cfg = {}
    for line in cfg_text.splitlines():
        line = line.strip()
        if ':' in line and not line.startswith('#') and not line.startswith('-'):
            k, _, v = line.partition(':')
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    stream_section = {}
    in_stream = False
    for line in cfg_text.splitlines():
        stripped = line.strip()
        if stripped == 'stream:':
            in_stream = True
        elif in_stream and stripped.startswith('path:'):
            stream_section['path'] = stripped.partition(':')[2].strip().strip('"').strip("'")
            in_stream = False
    cfg['stream'] = stream_section

baseline = cfg.get('baseline', 'PatchCore')
baseline_path = cfg.get('baseline_path', 'external/patchcore-inspection')
dataset_root = cfg.get('dataset_root', 'data/mvtec_ad')
category = cfg.get('category', 'bottle')
stream_type = cfg.get('stream_type', 'iid')
stream_path = (cfg.get('stream') or {}).get('path', 'results/latest/stream_smoke.json')
print(baseline, baseline_path, dataset_root, category, stream_type, stream_path)
PY
)

SCORES_CSV="results/latest/scores.csv"
LATEST_RUN="results/latest/latest_run.json"
MANIFEST="results/latest/manifest.json"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p results/latest

BASELINE_REPO_URL="TBD"
BASELINE_COMMIT_HASH="TBD"
if [ -d "${SMOKE_BASELINE_PATH}/.git" ]; then
  BASELINE_REPO_URL="$(git -C "${SMOKE_BASELINE_PATH}" remote get-url origin 2>/dev/null || echo TBD)"
  BASELINE_COMMIT_HASH="$(git -C "${SMOKE_BASELINE_PATH}" rev-parse HEAD 2>/dev/null || echo TBD)"
fi

echo "=== Smoke Run: ${SMOKE_BASELINE} / ${SMOKE_CATEGORY} ==="
echo "Config: ${CONFIG_FILE}"
echo ""

# --- Gate 1: Check baseline clone ---
SETUP_COMPLETE=true
if [ ! -d "${SMOKE_BASELINE_PATH}" ]; then
  echo "MISSING BASELINE: ${SMOKE_BASELINE_PATH} not found." >&2
  echo "  Expected path/URL/commit: see experiments/configs/baselines.yaml" >&2
  echo "  Run: bash scripts/setup_baselines.sh" >&2
  SETUP_COMPLETE=false
fi

# --- Gate 2: Check dataset ---
if [ ! -d "${SMOKE_DATASET_ROOT}/${SMOKE_CATEGORY}" ]; then
  echo "MISSING DATA: ${SMOKE_DATASET_ROOT}/${SMOKE_CATEGORY} not found." >&2
  echo "  Place the dataset under data/ (gitignored). See data/README.md." >&2
  SETUP_COMPLETE=false
fi

# --- Write setup_incomplete provenance if either gate failed ---
if [ "$SETUP_COMPLETE" = "false" ]; then
  echo ""
  echo "Status: setup_incomplete — writing non-final provenance (paper_allowed=false)."
  python3 - \
    "$SMOKE_BASELINE" "$SMOKE_BASELINE_PATH" "$BASELINE_REPO_URL" "$BASELINE_COMMIT_HASH" "$SMOKE_DATASET_ROOT" \
    "$SMOKE_CATEGORY" "$SMOKE_STREAM_TYPE" "$SMOKE_STREAM_PATH" \
    "$LATEST_RUN" "$MANIFEST" "$NOW" <<'PY'
import json, pathlib, sys
args = sys.argv[1:]
baseline, bpath, repo_url, commit_hash, droot, cat, stype, spath, run_path, mpath, ts = args
run = {
    "status": "setup_incomplete",
    "baseline": baseline,
    "baseline_path": bpath,
    "baseline_repo_url": repo_url,
    "baseline_commit_hash": commit_hash,
    "dataset": "MVTec AD",
    "dataset_root": droot,
    "category": cat,
    "stream_type": stype,
    "stream_path": spath,
    "prevalence": 0.05,
    "contamination_epsilon": 0,
    "command": "bash scripts/run_smoke.sh",
    "timestamp": ts,
    "paper_allowed": False,
    "notes": "setup_incomplete: baseline or dataset missing. Not a first-success run."
}
pathlib.Path(run_path).write_text(json.dumps(run, indent=2))
manifest = json.loads(pathlib.Path(mpath).read_text())
manifest["status"] = "setup_incomplete"
manifest["paper_allowed"] = False
pathlib.Path(mpath).write_text(json.dumps(manifest, indent=2))
print(f"Wrote setup_incomplete provenance to {run_path} and {mpath}.")
PY
  echo ""
  echo "RESULT: setup_incomplete. This is NOT first success gate A." >&2
  echo "        Configure baseline and dataset, then rerun." >&2
  exit 1
fi

# --- Gate 3: Run wrapper (only reached when baseline + dataset are present) ---
echo "Baseline and dataset found. Running wrapper..."
python3 - "$SMOKE_BASELINE" "$SMOKE_STREAM_PATH" "$SMOKE_DATASET_ROOT" "$SCORES_CSV" "$SMOKE_CATEGORY" "$SMOKE_STREAM_TYPE" <<'PY'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
baseline, stream_path, dataset_root, output_csv, category, stream_type = sys.argv[1:]
module_name = baseline.lower()
try:
    import importlib
    mod = importlib.import_module(f"experiments.baselines.{module_name}")
except ImportError as e:
    raise SystemExit(f"Cannot import wrapper experiments.baselines.{module_name}: {e}")
config = {"baseline": baseline, "category": category, "stream_type": stream_type}
mod.run(stream_path, dataset_root, output_csv, config)
PY

echo "Wrapper returned. Validating output..."

# --- Validate scores.csv schema ---
python3 - "$SCORES_CSV" <<'PY'
import csv, pathlib, sys
REQUIRED = ["stream_index","image_path","label","category","anomaly_score","latency_ms","peak_vram_mb","status"]
path = pathlib.Path(sys.argv[1])
if not path.exists():
    raise SystemExit(f"scores.csv not found at {path}")
header = next(csv.reader(path.open()))
if header != REQUIRED:
    raise SystemExit(f"scores.csv header mismatch.\n  Expected: {REQUIRED}\n  Got:      {header}")
rows = list(csv.DictReader(path.open()))
real_rows = [r for r in rows if r.get("status") != "placeholder_not_measured"]
if not real_rows:
    raise SystemExit("No non-placeholder rows in scores.csv. Not first success gate A.")
print(f"scores.csv valid: {len(real_rows)} non-placeholder row(s).")
PY

# --- Write success provenance ---
python3 - \
  "$SMOKE_BASELINE" "$SMOKE_BASELINE_PATH" "$BASELINE_REPO_URL" "$BASELINE_COMMIT_HASH" "$SMOKE_DATASET_ROOT" \
  "$SMOKE_CATEGORY" "$SMOKE_STREAM_TYPE" "$SMOKE_STREAM_PATH" \
  "$LATEST_RUN" "$MANIFEST" "$NOW" <<'PY'
import json, pathlib, sys
baseline, bpath, repo_url, commit_hash, droot, cat, stype, spath, run_path, mpath, ts = sys.argv[1:]
run = {
    "status": "success",
    "baseline": baseline,
    "baseline_path": bpath,
    "baseline_repo_url": repo_url,
    "baseline_commit_hash": commit_hash,
    "dataset": "MVTec AD",
    "dataset_root": droot,
    "category": cat,
    "stream_type": stype,
    "stream_path": spath,
    "prevalence": 0.05,
    "contamination_epsilon": 0,
    "command": "bash scripts/run_smoke.sh",
    "timestamp": ts,
    "paper_allowed": False,
    "notes": "First success gate A passed. paper_allowed stays false until measured results are reviewed."
}
pathlib.Path(run_path).write_text(json.dumps(run, indent=2))
manifest_path = pathlib.Path(mpath)
manifest = json.loads(manifest_path.read_text())
manifest["status"] = "first_success_a"
manifest["paper_allowed"] = False
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Wrote success provenance to {run_path} and {mpath}.")
PY

echo ""
echo "RESULT: First success gate A passed."
echo "  scores.csv: ${SCORES_CSV}"
echo "  latest_run: ${LATEST_RUN}"
echo ""
echo "NOTE: paper_allowed remains false until measured results are reviewed"
echo "      for paper eligibility."
