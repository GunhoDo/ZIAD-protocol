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

This renders checked result CSVs into LaTeX tables. With no arguments it
refreshes the compact P0 smoke summary, the MVTec quick-sweep smoke table, and
the MVTec/VisA stream/epsilon/calibration smoke tables for PatchCore, WinCLIP,
AnomalyCLIP, and RareCLIP. All generated tables are explicitly marked non-final
and paper-ineligible because `paper_allowed` remains `false`.

The compact summary artifacts are:

- `results/latest/tables/p0_smoke_summary.csv`
- `results/latest/tables/p0_smoke_summary_manifest.json`
- `results/latest/tables/p0_smoke_summary.tex`
- `results/latest/tables/paper_input_contract.json`

The compact summary includes the `memory_policy` axis. Current smoke evidence
contains `default/SCS` plus measured `MVTec AD × RareCLIP × FIFO`,
`MVTec AD × RareCLIP × Reservoir`/`Prototype-EMA`,
`VisA × RareCLIP × FIFO`/`Reservoir`/`Prototype-EMA`, and
`VisA × PatchCore × FIFO`/`Reservoir`/`Prototype-EMA` plus
`MVTec AD × PatchCore × FIFO`/`Reservoir`/`Prototype-EMA`
memory-policy shards. Memory-policy smoke shard coverage is complete, but
these remain paper-ineligible until reviewed full P0 runs exist.

`paper_input_contract.json` is the current paper table/figure input contract:
it lists generated table sources, row counts, source manifests, whether a table
is included by `paper/paper.tex`, and keeps `claim_allowed=false` while the
results are smoke-only.

## Refresh placeholder P0 outputs

```bash
bash scripts/run_p0.sh
# or
make p0
```

This refreshes placeholder files under `results/latest/`; it does not run real model inference and does not create measured findings.

## Plan current P0 shards

```bash
python3 experiments/p0_shards.py plan experiments/configs/p0.yaml \
  --output results/latest/p0_shards/manifest.json
python3 experiments/p0_shards.py execution-plan experiments/configs/p0.yaml \
  --output results/latest/p0_shards/execution_plan.json
python3 experiments/p0_shards.py verify results/latest/p0_shards/manifest.json \
  --require-outputs
```

This writes an orchestration manifest that maps the intended P0 matrix onto the
currently implemented all-category smoke matrix runners. It also records which
temperature-scaling calibration shards are implemented separately from the base
stream/epsilon shards. It creates no metrics, keeps `paper_allowed=false`, and
records unsupported or missing dimensions explicitly.

`execution_plan.json` is a restartable local execution manifest over those
shards. It fixes the order as base stream/epsilon shards, then memory-policy
shards, then calibration shards, records aggregate outputs for skip/resume, and
keeps `claim_allowed=false`.

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

## Run the VisA WinCLIP smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_winclip.csv \
  --latest-run results/latest/latest_run_visa_winclip.json \
  --output results/latest/metrics_visa_winclip.csv \
  --manifest results/latest/manifest_visa_winclip.json
```

This validates the VisA adapter on `data/visa/1cls/candle` with a length-20,
iid, epsilon-zero stream. It is measured smoke evidence only and keeps
`paper_allowed=false`.

## Run the VisA PatchCore smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_visa_patchcore.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_patchcore.csv \
  --latest-run results/latest/latest_run_visa_patchcore.json \
  --output results/latest/metrics_visa_patchcore.csv \
  --manifest results/latest/manifest_visa_patchcore.json
```

This validates PatchCore on `data/visa/1cls/candle` with the same length-20,
iid, epsilon-zero stream contract. The smoke config uses `sampler: random`
because the default approximate greedy coreset path is valid but much slower on
CPU. Outputs remain paper-ineligible with `paper_allowed=false`.

## Run the VisA WinCLIP mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_winclip_mini_matrix.yaml
```

This runs WinCLIP on VisA candle for `iid/bursty × ε 0/0.01/0.05`, length-20
streams. It writes aggregate metrics and CRD-lite smoke summaries under
`results/latest/visa_mini_matrix/`; these outputs are still paper-ineligible.

## Run the VisA PatchCore mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_patchcore_mini_matrix.yaml
```

This runs PatchCore on VisA candle for `iid/bursty × ε 0/0.01/0.05`,
length-20 streams. It uses `baseline_options.sampler: random` to keep the smoke
runtime bounded, then writes aggregate metrics and CRD-lite smoke summaries
under `results/latest/visa_patchcore_mini_matrix/`; these outputs are still
paper-ineligible.

## Run the VisA full-category WinCLIP smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_winclip.sh
```

This expands VisA coverage to all 12 local `data/visa/1cls` categories for
WinCLIP with iid, epsilon-zero, length-20 streams. It writes aggregate metrics
and CRD-lite smoke summaries under
`results/latest/visa_full_category_sweep_winclip/`; these outputs are still
smoke evidence with `paper_allowed=false`.

## Run the VisA full-category AnomalyCLIP smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_anomalyclip.sh
```

This uses the same all-12-category VisA smoke shape for AnomalyCLIP with iid,
epsilon-zero, length-20 streams. It is CPU single-image inference and remains
smoke evidence with `paper_allowed=false`.

## Run the VisA full-category PatchCore smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_patchcore.sh
```

This uses the same all-12-category VisA smoke shape for PatchCore with iid,
epsilon-zero, length-20 streams. It uses `baseline_options.sampler: identity` to
avoid the slow upstream coreset subsampling step; `run_smoke.sh` forwards these
baseline-specific YAML options into the wrapper. The aggregate output remains
smoke evidence with `paper_allowed=false`.

## Run the VisA full-category RareCLIP smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_rareclip.sh
```

This uses the same all-12-category VisA smoke shape for RareCLIP with iid,
epsilon-zero, length-20 streams. It exercises the online memory update path and
remains smoke evidence with `paper_allowed=false`.

## Run the VisA full-category stream/epsilon matrices

```bash
bash scripts/run_visa_full_category_stream_matrix_winclip.sh
bash scripts/run_visa_full_category_stream_matrix_winclip_temperature.sh
bash scripts/run_visa_full_category_stream_matrix_anomalyclip.sh
bash scripts/run_visa_full_category_stream_matrix_anomalyclip_temperature.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_fifo.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_prototype_ema.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_reservoir.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_temperature.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_fifo.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_prototype_ema.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_reservoir.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_temperature.sh
```

Each command runs one baseline over all 12 local VisA categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. The aggregate outputs live
under `results/latest/visa_full_category_stream_matrix_<baseline>/` and remain
smoke evidence with `paper_allowed=false`. The temperature runners add the
`calibration none/temperature_scaling` axis and write to separate
`results/latest/visa_full_category_stream_matrix_<baseline>_temperature/`
roots. They materialize from the corresponding measured non-temperature stream
matrix and apply deterministic calibration postprocessing, so they do not rerun
baseline inference for calibration variants.

The RareCLIP FIFO, Reservoir, and Prototype-EMA runners plus the PatchCore FIFO,
Reservoir, and Prototype-EMA runners are memory-policy shards over the same all-category VisA stream/epsilon
smoke shape. They write to separate
`results/latest/visa_full_category_stream_matrix_<baseline>_<policy>/` roots
and are tracked separately from the default/SCS and calibration shards.

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

## Run the MVTec full-category WinCLIP stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_winclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_winclip_temperature.sh
```

This runs WinCLIP across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. It writes aggregate metrics
and CRD-lite summaries only; generated per-run details remain ignored. The
temperature runner adds the `calibration none/temperature_scaling` axis by
materializing from measured non-temperature scores.

## Run the MVTec full-category AnomalyCLIP stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_anomalyclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_anomalyclip_temperature.sh
```

This runs AnomalyCLIP across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. The temperature runner adds
the `calibration none/temperature_scaling` axis without rerunning inference. It
is CPU single-image inference and remains smoke evidence with
`paper_allowed=false`.

## Run the MVTec full-category RareCLIP stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_rareclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_fifo.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_reservoir.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_prototype_ema.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_temperature.sh
```

This runs RareCLIP across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. The temperature runner adds
the `calibration none/temperature_scaling` axis without rerunning inference. It
exercises the online memory update path. The FIFO runner is the separate
RareCLIP memory-policy shard over the same stream/epsilon shape, and the
Reservoir runner records the corresponding bounded reservoir memory-policy
shard. The Prototype-EMA runner records the bounded prototype memory-policy
shard. All outputs
remain smoke evidence with `paper_allowed=false`.

## Run the MVTec full-category PatchCore stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_patchcore.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_fifo.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_reservoir.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_prototype_ema.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_temperature.sh
```

This runs PatchCore across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. It uses the train/good
offline batch-amortized smoke path and an ignored local fitted-model cache to
avoid rebuilding the same per-category support index for every stream condition.
The FIFO, Reservoir, and Prototype-EMA runners record separate bounded
feature-bank memory-policy shards and remain smoke evidence with
`paper_allowed=false`.
The temperature runner adds the `calibration none/temperature_scaling` axis
without rerunning inference. It remains smoke evidence with `paper_allowed=false`.

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
