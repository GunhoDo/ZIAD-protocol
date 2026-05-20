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

The build script produces `paper/paper.pdf`. If no LaTeX engine is installed, it writes a dependency-free placeholder PDF that preserves the TODO/no-fake-results rule.

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
