# Experiment PRD: Portable Baseline Setup for ZIAD

This document is the canonical experiment reference. A fresh git clone of this
repository should be fully explained by this file plus `README.md`, without
depending on `.omx/` planning state.

---

## Project Purpose

ZIAD evaluates how zero-shot and training-light industrial anomaly detection
baselines perform under realistic deployment conditions: streaming images with
configurable prevalence, contamination, and memory constraints. PatchCore is
treated as a training-light reference baseline; WinCLIP, AnomalyCLIP, and
RareCLIP are treated as CLIP-style baselines.

**Smoke-first strategy**: The first real experiment success is deliberately small:
one baseline + one dataset category produces `results/latest/scores.csv` using
the common score CSV schema. Full P0 scope is documented below but is not
required for first success.

---

## Runnable Now / TBD Later

| Component | Status |
|---|---|
| `docs/experiment-prd.md` (this file) | **Runnable now** |
| `.gitignore` with data/external/checkpoint rules | **Runnable now** |
| `data/README.md`, `external/README.md` | **Runnable now** |
| `experiments/configs/smoke.yaml` | **Runnable now** |
| `experiments/configs/baselines.yaml` | **Runnable now** (repo URLs/commits pinned from current local clones; wrappers/checkpoints may still be TBD) |
| `experiments/baselines/` wrapper stubs | **Runnable now** (stubs raise clear setup errors) |
| `scripts/setup_baselines.sh` | **Runnable now** (checks current clone slots and prints pinned clone commands if missing) |
| `scripts/run_smoke.sh` | **Runnable now** (fails explicitly if baseline/data missing) |
| Actual baseline repo URLs and commit hashes | **Pinned** — see `experiments/configs/baselines.yaml` |
| Real baseline clones under `external/` | **Present locally** — gitignored, not committed |
| Real datasets under `data/` | **TBD** — download and place locally |
| Real checkpoint files | **TBD** — obtain where the selected baseline requires them |
| First success gate A (real scores.csv) | **TBD** — requires wrapper integration + real data |
| Full P0 matrix | **TBD** — future path after first success |

---

## Baseline Clone Layout

All four P0 baselines are cloned locally under `external/` (gitignored):

```
external/
  RareCLIP/              # https://github.com/hjf02/RareCLIP.git
  patchcore-inspection/  # https://github.com/amazon-science/patchcore-inspection.git
  WinClip/               # https://github.com/caoyunkang/WinClip.git
  AnomalyCLIP/           # https://github.com/zqhang/AnomalyCLIP.git
```

Repo URLs and commit hashes are pinned in `experiments/configs/baselines.yaml`
from the current local clones. Do not fabricate replacement URLs or commit
hashes.

See `experiments/configs/baselines.yaml` for the full registry.
See `scripts/setup_baselines.sh` for clone slot status and pinned clone commands.

---

## Dataset Layout

All datasets live under `data/` (gitignored — not committed):

```
data/
  mvtec_ad/        # MVTec Anomaly Detection dataset
    bottle/
    cable/
    ...
  visa/            # VisA dataset
    candle/
    capsules/
    ...
```

Real data must be present before running first success gate A.
See `data/README.md` for download links and layout details.

---

## Common Score CSV Schema

Every baseline wrapper must produce rows conforming to this schema:

```
stream_index,image_path,label,category,anomaly_score,latency_ms,peak_vram_mb,status
```

Field notes:
- `stream_index`: integer index within the stream
- `image_path`: relative path to the evaluated image
- `label`: ground-truth label (0=normal, 1=anomaly)
- `category`: dataset category (e.g., `bottle`)
- `anomaly_score`: float anomaly score from the model
- `latency_ms`: per-image inference latency in milliseconds
- `peak_vram_mb`: peak VRAM usage in MB during inference
- `status`: wrapper-status extension — `measured` for real rows, `placeholder_not_measured` for non-final placeholders

The `status` column is a wrapper-status extension for setup and placeholder safety.
It is **not** a fabricated metric and must not be used as a model output.

---

## Wrapper Contract

Each baseline exposes a module-level `run` function:

```python
def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    """Write common score CSV rows or raise a clear setup error."""
```

Until a baseline is configured and cloned:
- Wrappers **raise a `RuntimeError`** with a clear message explaining what is missing.
- Wrappers **do not write fake anomaly scores**.

See `experiments/baselines/base.py` for the abstract interface and
`experiments/baselines/patchcore.py` for an example stub.

---

## Three Experiment Gates

### Gate 1: Setup Smoke Gate

**Condition**: docs/config/scripts exist; missing-baseline mode is explicit and non-final.

**Pass criteria**:
- All files in this PRD exist in the repo.
- `bash scripts/run_smoke.sh` in missing-baseline mode exits with a clear error
  or writes `status: setup_incomplete` — it does **not** fabricate scores.
- `paper_allowed` remains `false`.

**This is the current state of the repository.**

### Gate 2: First Success Gate A

**Condition**: One configured baseline + one real dataset category + one consumed or
generated stream file (`results/latest/stream_smoke.json`) produces schema-valid
`results/latest/scores.csv` with non-placeholder rows.

**Pass criteria**:
- The configured baseline `local_path` is present (baseline cloned and configured).
- `data/mvtec_ad/bottle/` (or configured category) is present.
- `bash scripts/run_smoke.sh` completes without error.
- `results/latest/scores.csv` has the required header and at least one row with
  `status=measured` (not `placeholder_not_measured`).
- `results/latest/latest_run.json` records baseline provenance, dataset/category,
  stream_path, command, and `paper_allowed: false`.

**Not yet achieved. Requires wrapper integration + dataset download.**

### Gate 3: Paper Gate

**Condition**: Only real measured final outputs may set `manifest.paper_allowed=true`.

**Pass criteria**:
- Baseline repo URL and commit hash are pinned (not TBD).
- Real non-placeholder scores exist in `results/latest/scores.csv`.
- `results/latest/latest_run.json` has pinned `baseline_repo_url` and `baseline_commit_hash`.
- A human reviewer has approved the outputs for paper inclusion.

**Not yet achieved.**

---

## results/latest/ Tracking Policy

Track lightweight paper-facing files only:

| Tracked | Reason |
|---|---|
| `manifest.json` | Paper eligibility contract |
| `latest_run.json` | Run provenance |
| `scores.csv` | Score contract (placeholder or real) |
| `metrics.csv` | Metric contract (placeholder or real) |
| `tables/**` | Paper-facing LaTeX tables |
| `figures/**` | Paper-facing figure files |

Ignored by default (gitignored):

| Ignored | Reason |
|---|---|
| `raw/**`, `logs/**` | Bulky generated dumps |
| `streams/**` | Generated stream files |
| `*.npy`, `*.npz`, `*.pt`, `*.pth` | Tensor/checkpoint artifacts |
| `archive/**` | Optional historical copies |

Placeholder/TODO files may be tracked only when they are visibly non-final and
keep `paper_allowed=false`. Real measured artifacts may be promoted into tracked
`results/latest/` only when small, paper-facing, and supported by `latest_run.json`.

---

## No-Fake-Results Rule

Do not place fabricated metrics in:
- `paper/paper.md`
- `paper/paper.tex`
- `paper/paper.pdf`
- `results/latest/scores.csv` (placeholder rows must use `status=placeholder_not_measured`)
- `results/latest/latest_run.json`

Missing or unrun results must remain TODO/placeholder with `paper_allowed=false`.

---

## .omx/ Is Planning History Only

The `.omx/` directory contains deep-interview specs, ralplan drafts, and planning
artifacts. It is **not** the source of truth for experiment setup. This file
(`docs/experiment-prd.md`) and the other git-tracked files are the canonical reference.

---

## Full P0 Scope (Future Path)

The following is documented for future reference. It is **not required for first success**.

- **Datasets**: MVTec AD, VisA
- **Streams**: i.i.d., bursty
- **Prevalence**: 0.05
- **Contamination ε**: 0, 0.01, 0.05
- **Baselines**: RareCLIP, PatchCore, WinCLIP, AnomalyCLIP
- **Memory policies** (RareCLIP/PatchCore): default/SCS, FIFO, Reservoir, Prototype-EMA
- **Calibration**: none, temperature scaling
- **Metrics**: Image AUROC, AUPR, ECE, latency, CRD-lite

See `experiments/configs/p0.yaml` for the full matrix configuration.
