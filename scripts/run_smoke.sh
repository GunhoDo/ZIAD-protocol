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
IFS=$'\t' read -r SMOKE_BASELINE SMOKE_BASELINE_PATH SMOKE_DATASET SMOKE_DATASET_ROOT SMOKE_CATEGORY SMOKE_STREAM_TYPE SMOKE_STREAM_PATH SMOKE_PREVALENCE SMOKE_EPSILON SMOKE_MEMORY_POLICY SMOKE_CALIBRATION SMOKE_STREAM_SEED SMOKE_STREAM_LENGTH SMOKE_BURST_LENGTH SCORES_CSV LATEST_RUN MANIFEST SMOKE_SCORING_MODE SMOKE_LATENCY_SEMANTICS SMOKE_TRAINING_SOURCE SMOKE_STREAM_SOURCE < <(python3 - "$CONFIG_FILE" <<'PY'
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
    for raw in cfg_text.splitlines():
        if raw.strip() == 'stream:':
            in_stream = True
            continue
        if in_stream:
            if raw and not raw.startswith(' ') and not raw.startswith('\t'):
                in_stream = False
                continue
            stripped = raw.strip()
            if ':' in stripped and not stripped.startswith('#'):
                k, _, v = stripped.partition(':')
                stream_section[k.strip()] = v.strip().strip('\"').strip("'") or None
    cfg['stream'] = stream_section

baseline = cfg.get('baseline', 'PatchCore')
baseline_path = cfg.get('baseline_path', 'external/patchcore-inspection')
dataset = cfg.get('dataset', 'MVTec AD')
dataset_root = cfg.get('dataset_root', 'data/mvtec_ad')
category = cfg.get('category', 'bottle')
stream_type = cfg.get('stream_type', 'iid')
stream = cfg.get('stream') or {}
stream_path = stream.get('path', 'results/latest/stream_smoke.json')
prevalence = cfg.get('prevalence', 0.05)
epsilon = cfg.get('contamination_epsilon', 0)
memory_policy = cfg.get('memory_policy', 'default/SCS')
calibration = cfg.get('calibration', 'none')
seed = stream.get('seed', 0)
length = stream.get('length')
burst_length = stream.get('burst_length', 1)
outputs = cfg.get('outputs') or {}
scores_csv = outputs.get('scores_csv', 'results/latest/scores.csv')
latest_run = outputs.get('latest_run', 'results/latest/latest_run.json')
manifest = outputs.get('manifest', 'results/latest/manifest.json')
provenance = cfg.get('provenance') or {}
scoring_mode = provenance.get('scoring_mode', 'stream_ordered_offline')
latency_semantics = provenance.get('latency_semantics', 'offline_batch_amortized')
training_source = provenance.get('training_source', 'train/good')
stream_source = provenance.get('stream_source', 'test/*')
length = '__NONE__' if length in {None, '', 'null', 'None'} else length
print("\t".join(str(value) for value in [
    baseline, baseline_path, dataset, dataset_root, category, stream_type, stream_path,
    prevalence, epsilon, memory_policy, calibration, seed, length, burst_length, scores_csv, latest_run,
    manifest, scoring_mode, latency_semantics, training_source, stream_source,
]))
PY
)

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p results/latest
mkdir -p "$(dirname "$SCORES_CSV")" "$(dirname "$LATEST_RUN")" "$(dirname "$MANIFEST")" "$(dirname "$SMOKE_STREAM_PATH")"

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
if [ ! -d "${SMOKE_DATASET_ROOT}/${SMOKE_CATEGORY}" ] && [ ! -d "${SMOKE_DATASET_ROOT}/1cls/${SMOKE_CATEGORY}" ]; then
  echo "MISSING DATA: ${SMOKE_DATASET_ROOT}/${SMOKE_CATEGORY} not found." >&2
  echo "  Place the dataset under data/ (gitignored). See data/README.md." >&2
  SETUP_COMPLETE=false
fi

# --- Write setup_incomplete provenance if either gate failed ---
if [ "$SETUP_COMPLETE" = "false" ]; then
  echo ""
  echo "Status: setup_incomplete — writing non-final provenance (paper_allowed=false)."
  python3 - \
    "$SMOKE_BASELINE" "$SMOKE_BASELINE_PATH" "$BASELINE_REPO_URL" "$BASELINE_COMMIT_HASH" "$SMOKE_DATASET" "$SMOKE_DATASET_ROOT" \
    "$SMOKE_CATEGORY" "$SMOKE_STREAM_TYPE" "$SMOKE_STREAM_PATH" \
    "$SMOKE_PREVALENCE" "$SMOKE_EPSILON" "$SMOKE_MEMORY_POLICY" "$SMOKE_CALIBRATION" "$SMOKE_STREAM_SEED" "$SMOKE_STREAM_LENGTH" "$SMOKE_BURST_LENGTH" \
    "$LATEST_RUN" "$MANIFEST" "$NOW" "$SMOKE_SCORING_MODE" "$SMOKE_LATENCY_SEMANTICS" "$SMOKE_TRAINING_SOURCE" "$SMOKE_STREAM_SOURCE" <<'PY'
import json, pathlib, sys
args = sys.argv[1:]
baseline, bpath, repo_url, commit_hash, dataset, droot, cat, stype, spath, prevalence, epsilon, memory_policy, calibration, seed, length, burst_length, run_path, mpath, ts, scoring_mode, latency_semantics, training_source, stream_source = args
stream_metadata = {}
run = {
    "status": "setup_incomplete",
    "baseline": baseline,
    "baseline_path": bpath,
    "baseline_repo_url": repo_url,
    "baseline_commit_hash": commit_hash,
    "dataset": dataset,
    "dataset_root": droot,
    "category": cat,
    "stream_type": stype,
    "stream_path": spath,
    "prevalence": float(prevalence),
    "contamination_epsilon": float(epsilon),
    "memory_policy": memory_policy,
    "calibration": calibration,
    "stream_seed": int(seed),
    "stream_length": None if length == "__NONE__" else int(length),
    "burst_length": int(burst_length),
    "scoring_mode": scoring_mode,
    "latency_semantics": latency_semantics,
    "training_source": training_source,
    "stream_source": stream_source,
    "stream_metadata": {
        key: stream_metadata.get(key)
        for key in [
            "target_anomaly_fraction", "applied_anomaly_fraction",
            "applied_epsilon_equivalent", "requested_stream_length",
            "applied_stream_length", "selected_normal_count",
            "selected_anomaly_count", "applied_burst_count",
            "applied_burst_lengths", "applied_max_burst_length", "warnings",
        ]
        if key in stream_metadata
    },
    "command": "bash scripts/run_smoke.sh",
    "timestamp": ts,
    "paper_allowed": False,
    "notes": "setup_incomplete: baseline or dataset missing. Not a first-success run."
}
pathlib.Path(run_path).write_text(json.dumps(run, indent=2))
manifest_path = pathlib.Path(mpath)
manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
manifest["status"] = "setup_incomplete"
manifest["paper_allowed"] = False
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Wrote setup_incomplete provenance to {run_path} and {mpath}.")
PY
  echo ""
  echo "RESULT: setup_incomplete. This is NOT first success gate A." >&2
  echo "        Configure baseline and dataset, then rerun." >&2
  exit 1
fi

# --- Gate 3: Generate stream (only reached when baseline + dataset are present) ---
echo "Baseline and dataset found. Generating stream..."
STREAM_ARGS=(
  --dataset-root "$SMOKE_DATASET_ROOT"
  --dataset "$SMOKE_DATASET"
  --category "$SMOKE_CATEGORY"
  --stream-type "$SMOKE_STREAM_TYPE"
  --prevalence "$SMOKE_PREVALENCE"
  --contamination-epsilon "$SMOKE_EPSILON"
  --seed "$SMOKE_STREAM_SEED"
  --burst-length "$SMOKE_BURST_LENGTH"
  --output "$SMOKE_STREAM_PATH"
)
if [ "$SMOKE_STREAM_LENGTH" != "__NONE__" ]; then
  STREAM_ARGS+=(--length "$SMOKE_STREAM_LENGTH")
fi
python3 experiments/make_streams.py "${STREAM_ARGS[@]}"

python3 - "$SMOKE_STREAM_PATH" "$SMOKE_SCORING_MODE" "$SMOKE_LATENCY_SEMANTICS" "$SMOKE_TRAINING_SOURCE" "$SMOKE_STREAM_SOURCE" <<'PY'
import json, pathlib, sys

path = pathlib.Path(sys.argv[1])
scoring_mode, latency_semantics, training_source, stream_source = sys.argv[2:]
payload = json.loads(path.read_text())
metadata = payload.setdefault("metadata", {})
metadata["scoring_mode"] = scoring_mode
metadata["latency_semantics"] = latency_semantics
metadata["training_source"] = training_source
metadata["stream_source"] = stream_source
path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
PY

# --- Gate 4: Run wrapper ---
echo "Running wrapper..."
python3 - "$CONFIG_FILE" "$SMOKE_BASELINE" "$SMOKE_STREAM_PATH" "$SMOKE_DATASET_ROOT" "$SCORES_CSV" "$SMOKE_DATASET" "$SMOKE_CATEGORY" "$SMOKE_STREAM_TYPE" "$SMOKE_SCORING_MODE" "$SMOKE_LATENCY_SEMANTICS" <<'PY'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
config_file, baseline, stream_path, dataset_root, output_csv, dataset, category, stream_type, scoring_mode, latency_semantics = sys.argv[1:]
module_name = baseline.lower()
try:
    import importlib
    mod = importlib.import_module(f"experiments.baselines.{module_name}")
except ImportError as e:
    raise SystemExit(f"Cannot import wrapper experiments.baselines.{module_name}: {e}")
try:
    import yaml
    loaded = yaml.safe_load(pathlib.Path(config_file).read_text()) or {}
    if not isinstance(loaded, dict):
        loaded = {}
except ImportError:
    loaded = {}
config = dict(loaded)
config.update({
    "baseline": baseline,
    "dataset": dataset,
    "dataset_root": dataset_root,
    "category": category,
    "stream_type": stream_type,
    "scoring_mode": scoring_mode,
    "latency_semantics": latency_semantics,
})
mod.run(stream_path, dataset_root, output_csv, config)
PY

echo "Wrapper returned. Validating output..."

# --- Validate scores.csv schema ---
python3 - "$SCORES_CSV" "$SMOKE_STREAM_PATH" <<'PY'
import csv, json, pathlib, sys
REQUIRED = ["stream_index","image_path","label","category","anomaly_score","latency_ms","peak_vram_mb","status"]
path = pathlib.Path(sys.argv[1])
stream_path = pathlib.Path(sys.argv[2])
if not path.exists():
    raise SystemExit(f"scores.csv not found at {path}")
header = next(csv.reader(path.open()))
if header != REQUIRED:
    raise SystemExit(f"scores.csv header mismatch.\n  Expected: {REQUIRED}\n  Got:      {header}")
rows = list(csv.DictReader(path.open()))
unknown_statuses = sorted({r.get("status", "") for r in rows} - {"measured", "placeholder_not_measured"})
if unknown_statuses:
    raise SystemExit(f"Unknown score row status value(s): {unknown_statuses}")
real_rows = [r for r in rows if r.get("status") == "measured"]
if not real_rows:
    raise SystemExit("No non-placeholder rows in scores.csv. Not first success gate A.")
if stream_path.exists():
    stream = json.loads(stream_path.read_text())
    stream_items = stream.get("items") or []
    if stream_items and len(real_rows) != len(stream_items):
        raise SystemExit(
            f"scores.csv row count {len(real_rows)} does not match stream item count {len(stream_items)}"
        )
print(f"scores.csv valid: {len(real_rows)} non-placeholder row(s).")
PY

# --- Write success provenance ---
python3 - \
  "$SMOKE_BASELINE" "$SMOKE_BASELINE_PATH" "$BASELINE_REPO_URL" "$BASELINE_COMMIT_HASH" "$SMOKE_DATASET" "$SMOKE_DATASET_ROOT" \
  "$SMOKE_CATEGORY" "$SMOKE_STREAM_TYPE" "$SMOKE_STREAM_PATH" \
  "$SMOKE_PREVALENCE" "$SMOKE_EPSILON" "$SMOKE_MEMORY_POLICY" "$SMOKE_CALIBRATION" "$SMOKE_STREAM_SEED" "$SMOKE_STREAM_LENGTH" "$SMOKE_BURST_LENGTH" \
  "$LATEST_RUN" "$MANIFEST" "$NOW" "$SMOKE_SCORING_MODE" "$SMOKE_LATENCY_SEMANTICS" "$SMOKE_TRAINING_SOURCE" "$SMOKE_STREAM_SOURCE" <<'PY'
import json, pathlib, sys
baseline, bpath, repo_url, commit_hash, dataset, droot, cat, stype, spath, prevalence, epsilon, memory_policy, calibration, seed, length, burst_length, run_path, mpath, ts, scoring_mode, latency_semantics, training_source, stream_source = sys.argv[1:]
stream_payload = json.loads(pathlib.Path(spath).read_text())
if not isinstance(stream_payload, dict) or not isinstance(stream_payload.get("metadata"), dict):
    raise SystemExit(f"Stream metadata missing or invalid in {spath}")
stream_metadata = stream_payload["metadata"]
run = {
    "status": "success",
    "baseline": baseline,
    "baseline_path": bpath,
    "baseline_repo_url": repo_url,
    "baseline_commit_hash": commit_hash,
    "dataset": dataset,
    "dataset_root": droot,
    "category": cat,
    "stream_type": stype,
    "stream_path": spath,
    "prevalence": float(prevalence),
    "contamination_epsilon": float(epsilon),
    "memory_policy": memory_policy,
    "calibration": calibration,
    "stream_seed": int(seed),
    "stream_length": None if length == "__NONE__" else int(length),
    "burst_length": int(burst_length),
    "scoring_mode": scoring_mode,
    "latency_semantics": latency_semantics,
    "training_source": training_source,
    "stream_source": stream_source,
    "stream_metadata": {
        key: stream_metadata.get(key)
        for key in [
            "target_anomaly_fraction", "applied_anomaly_fraction",
            "applied_epsilon_equivalent", "requested_stream_length",
            "applied_stream_length", "selected_normal_count",
            "selected_anomaly_count", "applied_burst_count",
            "applied_burst_lengths", "applied_max_burst_length", "warnings",
        ]
        if key in stream_metadata
    },
    "command": "bash scripts/run_smoke.sh",
    "timestamp": ts,
    "paper_allowed": False,
    "notes": "First success gate A passed. paper_allowed stays false until measured results are reviewed."
}
pathlib.Path(run_path).write_text(json.dumps(run, indent=2))
manifest_path = pathlib.Path(mpath)
manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
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
