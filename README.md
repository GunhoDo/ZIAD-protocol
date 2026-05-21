# ZIAD Protocol: Streaming Zero-Shot Anomaly Detection with CLIP

This repository contains the experiment setup and paper pipeline for CLIP ZSAD —
streaming zero-shot industrial anomaly detection benchmarked against P0 baselines.

The canonical experiment reference is [`docs/experiment-prd.md`](docs/experiment-prd.md).
The final paper artifact is `paper/paper.pdf`, which may only reference `results/latest/`.

## Experiment Setup (Smoke First)

```text
1. Place datasets under data/        (gitignored — download MVTec AD / VisA locally)
2. Clone baselines under external/   (gitignored — current URLs/commits pinned in baselines.yaml)
3. Run smoke:  bash scripts/run_smoke.sh
4. Run a mini-matrix: bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml
5. Build paper: make paper
```

- `data/` and `external/` are gitignored. Real datasets and baseline clones must be placed locally.
- Baseline repo URLs and commit hashes are pinned from current local clones (see `experiments/configs/baselines.yaml`).
- Use `bash scripts/setup_baselines.sh` to see per-baseline clone slot status and pinned clone commands.
- See [`docs/experiment-prd.md`](docs/experiment-prd.md) for the full experiment PRD including gates, schema, and P0 scope.

---

## Paper Pipeline

The final paper artifact:

## Build the paper

```bash
bash scripts/build_paper.sh
# or
make paper
```

The build script first refreshes generated tables under `results/latest/tables/`,
then produces `paper/paper.pdf`. If no LaTeX engine is installed, it writes a
dependency-free placeholder PDF that preserves the TODO/no-fake-results rule.

## Refresh paper-facing tables only

```bash
bash scripts/render_paper_tables.sh
# or
make paper-tables
```

This renders checked result CSVs into LaTeX tables. Current quick-sweep tables
are explicitly marked non-final and paper-ineligible because `paper_allowed`
remains `false`.

## Refresh placeholder P0 outputs

```bash
bash scripts/run_p0.sh
# or
make p0
```

This refreshes placeholder files under `results/latest/`; it does not run real model inference and does not create measured findings.

## Run a measured mini-matrix smoke

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml
```

Mini-matrix outputs are measured pipeline evidence but remain paper-ineligible:
`paper_allowed` must stay `false` until full reviewed P0 results exist.

The aggregate mini-matrix step also writes a CRD-lite smoke summary such as
`results/latest/mini_matrix/crd_lite_winclip_bottle.csv`. CRD-lite is derived
from epsilon-0 AUROC/AUPR drops and is diagnostic until full P0 review.

## Run the AnomalyCLIP bottle smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_anomalyclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_anomalyclip.csv \
  --latest-run results/latest/latest_run_anomalyclip.json \
  --output results/latest/metrics_anomalyclip.csv \
  --manifest results/latest/manifest_anomalyclip.json
```

This uses the local AnomalyCLIP checkpoint and the upstream image-level
`text_probs[:, 0, 1]` anomaly score on the project stream order. It remains
smoke evidence with `paper_allowed=false`.

## Run the RareCLIP bottle smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_rareclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_rareclip.csv \
  --latest-run results/latest/latest_run_rareclip.json \
  --output results/latest/metrics_rareclip.csv \
  --manifest results/latest/manifest_rareclip.json
```

This uses the local RareCLIP MVTec checkpoint and upstream
`process_image_and_update(..., update=True)` image-level anomaly score on the
project stream order. It remains smoke evidence with `paper_allowed=false`.

## Run the AnomalyCLIP bottle mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/anomalyclip_mini_matrix.yaml
```

This runs AnomalyCLIP on MVTec AD bottle for `iid/bursty × ε 0/0.01/0.05`,
then writes aggregate metrics and a CRD-lite smoke summary under
`results/latest/mini_matrix/`. It is measured smoke evidence only.

## Run the RareCLIP bottle mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/rareclip_mini_matrix.yaml
```

This runs RareCLIP on MVTec AD bottle for `iid/bursty × ε 0/0.01/0.05`,
then writes aggregate metrics and a CRD-lite smoke summary under
`results/latest/mini_matrix/`. It uses CPU single-image online inference in the
current local setup and remains paper-ineligible.

## Run a category quick sweep

```bash
bash scripts/run_category_quick_sweep.sh experiments/configs/category_quick_sweep.yaml
```

This runs a small PatchCore/WinCLIP × bottle/capsule/hazelnut smoke sweep to
catch category-specific failures before full P0. It is measured but still
paper-ineligible.

## Run the MVTec full-category WinCLIP smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep.sh
```

This expands the category coverage to all 15 MVTec AD categories for WinCLIP
with iid, epsilon-zero, length-20 streams. It is still smoke evidence, not a
full P0 result.

## Run the MVTec full-category PatchCore smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep_patchcore.sh
```

This uses the same all-category smoke shape for PatchCore. It exercises the
train/good setup and stream-ordered offline scoring path across all MVTec
categories. It is still smoke evidence and remains paper-ineligible.

## Run the MVTec full-category AnomalyCLIP smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep_anomalyclip.sh
```

This uses the same all-category smoke shape for AnomalyCLIP with iid,
epsilon-zero, length-20 streams. It is CPU single-image inference and remains
smoke evidence with `paper_allowed=false`.

## Run the MVTec full-category RareCLIP smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep_rareclip.sh
```

This uses the same all-category smoke shape for RareCLIP with iid,
epsilon-zero, length-20 streams. It is CPU single-image online inference and
remains smoke evidence with `paper_allowed=false`.

## Current result contract

- `results/latest/latest_run.json`: one current run/status summary.
- `results/latest/manifest.json`: one current list of paper-facing result files.
- `results/latest/scores.csv`: score CSV contract, currently placeholder.
- `results/latest/metrics.csv`: metric CSV contract, currently placeholder.

If `results/latest/manifest.json` is not `final` with `paper_allowed: true`, the Results section must stay TODO/placeholder.

## P0 scope

- Datasets: MVTec AD, VisA
- Streams: iid, bursty
- Prevalence: 0.05
- Contamination ε: 0, 0.01, 0.05
- Baselines: RareCLIP, PatchCore, WinCLIP, AnomalyCLIP
- Memory policies for RareCLIP/PatchCore: default/SCS, FIFO, Reservoir, Prototype-EMA
- Calibration: none, temperature scaling
- Metrics: Image AUROC, AUPR, ECE, latency, CRD-lite

## Result authenticity rule

Do not place fabricated metrics in `paper/paper.md`, `paper/paper.tex`, or `paper/paper.pdf`. Missing or unrun results must remain TODO/placeholder.
