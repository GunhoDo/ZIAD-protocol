# AGENTS.md — ZIAD Protocol

Project: **Streaming Zero-Shot Industrial Anomaly Detection with CLIP (CLIP ZSAD)**
Goal: Benchmark CLIP-based anomaly detection baselines under streaming conditions (i.i.d./bursty, prevalence 0.05, configurable contamination ε), publish results as an ACCV/LNCS paper.

Canonical experiment reference: [`docs/experiment-prd.md`](docs/experiment-prd.md)

---

## Current Status

**Setup smoke gate: PASSED** — docs, configs, scripts, and wrapper stubs exist.
**First success gate A: PASSED for PatchCore, WinCLIP, AnomalyCLIP, and RareCLIP smoke paths** — real stream files, measured score rows, iid/bursty × ε artifacts, CRD-lite smoke summaries, bottle/capsule/hazelnut PatchCore/WinCLIP quick-sweep artifacts, all-baseline all-15-category iid ε=0 smoke artifacts, CLIP bottle mini-matrix artifacts, PatchCore/WinCLIP/AnomalyCLIP/RareCLIP all-category stream/epsilon matrix artifacts, and VisA candle WinCLIP smoke/mini-matrix artifacts exist; not full P0.
**Paper gate: NOT YET** — current outputs remain smoke/mini-matrix evidence with `paper_allowed: false`; generated paper-facing tables are non-final smoke evidence only; full reviewed P0 results are still required.

Baseline repo URLs and commit hashes are pinned in `experiments/configs/baselines.yaml`
from the current local clones. Do not fabricate replacement URLs or commit hashes.

---

## Directory Layout

```
ZIAD-protocol/
  docs/experiment-prd.md      # Canonical experiment PRD — read this first
  README.md                   # Quickstart overview
  AGENTS.md                   # This file

  experiments/
    configs/
      smoke.yaml              # Smoke run: PatchCore + MVTec AD/bottle (one baseline/category)
      baselines.yaml          # Registry: 4 baselines with pinned repo_url/commit_hash
      category_quick_sweep.yaml # PatchCore/WinCLIP bottle/capsule/hazelnut quick sweep
      mvtec_full_category_sweep_anomalyclip.yaml # AnomalyCLIP all-category iid epsilon-zero smoke sweep
      mvtec_full_category_sweep_patchcore.yaml # PatchCore all-category iid epsilon-zero smoke sweep
      mvtec_full_category_sweep_rareclip.yaml # RareCLIP all-category iid epsilon-zero smoke sweep
      mvtec_full_category_sweep_winclip.yaml # WinCLIP all-category iid epsilon-zero smoke sweep
      mvtec_full_category_stream_matrix_anomalyclip.yaml # AnomalyCLIP all-category iid/bursty × epsilon smoke matrix
      mvtec_full_category_stream_matrix_patchcore.yaml # PatchCore all-category iid/bursty × epsilon smoke matrix
      mvtec_full_category_stream_matrix_rareclip.yaml # RareCLIP all-category iid/bursty × epsilon smoke matrix
      mvtec_full_category_stream_matrix_winclip.yaml # WinCLIP all-category iid/bursty × epsilon smoke matrix
      anomalyclip_mini_matrix.yaml # AnomalyCLIP bottle iid/bursty × epsilon smoke matrix
      rareclip_mini_matrix.yaml # RareCLIP bottle iid/bursty × epsilon smoke matrix
      smoke_anomalyclip.yaml # AnomalyCLIP bottle iid epsilon-zero smoke
      smoke_rareclip.yaml    # RareCLIP bottle iid epsilon-zero smoke
      smoke_visa_winclip.yaml # WinCLIP VisA candle iid epsilon-zero smoke
      visa_winclip_mini_matrix.yaml # WinCLIP VisA candle iid/bursty × epsilon smoke matrix
      winclip_mini_matrix.yaml # WinCLIP bottle iid/bursty × epsilon smoke matrix
      p0.yaml                 # Full P0 matrix (future path, not required for first success)
    baselines/
      base.py                 # BaselineWrapper ABC + _setup_error() helper
      patchcore.py            # Implemented PatchCore wrapper for stream-ordered MVTec smoke with fitted-model cache
      rareclip.py             # Implemented RareCLIP wrapper for stream-ordered MVTec smoke
      winclip.py              # Implemented WinCLIP wrapper for stream-ordered MVTec smoke
      anomalyclip.py          # Implemented AnomalyCLIP wrapper for stream-ordered MVTec smoke
    evaluate.py               # Score evaluator for smoke/mini-matrix metrics
    category_sweep.py         # Multi-category quick-sweep config/aggregate helper
    mini_matrix.py            # Baseline-parametric mini-matrix config/aggregate helper
    make_streams.py           # Deterministic MVTec/VisA stream generator (iid/bursty)
    render_paper_tables.py    # Renders paper-ineligible smoke evidence tables
    prepare_data.py           # Placeholder data prep
    run_baselines.py          # Placeholder baseline runner

  scripts/
    run_smoke.sh              # Smoke runner → results/latest/scores.csv (exits if baseline/data missing)
    run_baseline_mini_matrix.sh # Generic baseline mini-matrix runner
    run_category_quick_sweep.sh # PatchCore/WinCLIP category quick-sweep runner
    run_mvtec_full_category_sweep_anomalyclip.sh # AnomalyCLIP all-category MVTec smoke sweep runner
    run_mvtec_full_category_sweep.sh # WinCLIP all-category MVTec smoke sweep runner
    run_mvtec_full_category_sweep_patchcore.sh # PatchCore all-category MVTec smoke sweep runner
    run_mvtec_full_category_sweep_rareclip.sh # RareCLIP all-category MVTec smoke sweep runner
    run_mvtec_full_category_stream_matrix_anomalyclip.sh # AnomalyCLIP all-category stream/epsilon smoke matrix runner
    run_mvtec_full_category_stream_matrix_patchcore.sh # PatchCore all-category stream/epsilon smoke matrix runner
    run_mvtec_full_category_stream_matrix_rareclip.sh # RareCLIP all-category stream/epsilon smoke matrix runner
    run_mvtec_full_category_stream_matrix_winclip.sh # WinCLIP all-category stream/epsilon smoke matrix runner
    run_patchcore_mini_matrix.sh # Compatibility wrapper around generic mini-matrix runner
    render_paper_tables.sh    # Refreshes generated LaTeX tables from result CSVs
    setup_baselines.sh        # Checks clone slots and prints pinned clone commands if missing
    run_p0.sh                 # Refreshes P0 placeholder outputs (no real inference)
    build_paper.sh            # Builds paper/paper.pdf (or placeholder if no LaTeX)

  data/
    README.md                 # Dataset layout doc (gitignored except this file)
    mvtec_ad/                 # NOT committed — place locally
    visa/                     # NOT committed — place locally

  external/
    README.md                 # Baseline clone layout doc (gitignored except this file)
    RareCLIP/                 # NOT committed — current RareCLIP clone slot
    patchcore-inspection/     # NOT committed — current PatchCore clone slot
    WinClip/                  # NOT committed — current WinCLIP clone slot
    AnomalyCLIP/              # NOT committed — current AnomalyCLIP clone slot

  results/latest/
    scores.csv                # Score contract (currently placeholder)
    metrics.csv               # Metric contract (currently placeholder)
    latest_run.json           # Run provenance (status, baseline, dataset, paper_allowed)
    manifest.json             # Paper eligibility (paper_allowed: false until real results)
    tables/                   # Paper-facing LaTeX tables
    figures/                  # Paper-facing figures

  paper/
    paper.tex                 # Main LaTeX source
    paper.md                  # Markdown draft
    paper.pdf                 # Built artifact
    refs.bib                  # References

  Makefile                    # make paper | make p0 | make clean-paper
```

---

## Experiment Gates

### Gate 1: Setup Smoke (current state)
Docs/config/scripts exist. `bash scripts/run_smoke.sh` exits with `setup_incomplete` when baseline/data are missing. Does not fabricate scores.

### Gate 2: First Success A
One configured baseline + real dataset category + stream file → schema-valid `results/latest/scores.csv` with non-placeholder rows.
Requires:
1. Ensure the configured `local_path`, `repo_url`, and `commit_hash` in `experiments/configs/baselines.yaml` match the local clone.
2. Download dataset to `data/mvtec_ad/` (or configured root).
3. Implement `experiments/baselines/<baseline>.py` `run()` method.
4. `bash scripts/run_smoke.sh`

### Gate 3: Paper Gate
`manifest.paper_allowed=true` — only after real measured results are produced and reviewed. Placeholder outputs must keep `paper_allowed: false`.

---

## Key Commands

```bash
bash scripts/setup_baselines.sh   # Show clone-slot status for all 4 baselines
bash scripts/run_smoke.sh         # Smoke run (fails clearly if baseline/data missing)
bash scripts/run_smoke.sh experiments/configs/smoke_rareclip.yaml
bash scripts/run_smoke.sh experiments/configs/smoke_anomalyclip.yaml
bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip.yaml
bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml
bash scripts/run_baseline_mini_matrix.sh experiments/configs/anomalyclip_mini_matrix.yaml
bash scripts/run_baseline_mini_matrix.sh experiments/configs/rareclip_mini_matrix.yaml
bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_winclip_mini_matrix.yaml
bash scripts/run_category_quick_sweep.sh experiments/configs/category_quick_sweep.yaml
bash scripts/run_mvtec_full_category_sweep.sh
bash scripts/run_mvtec_full_category_sweep_patchcore.sh
bash scripts/run_mvtec_full_category_sweep_anomalyclip.sh
bash scripts/run_mvtec_full_category_sweep_rareclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_anomalyclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_winclip.sh
bash scripts/render_paper_tables.sh # Refresh paper-facing non-final smoke evidence tables
make paper                        # Build paper/paper.pdf
make p0                           # Refresh P0 placeholder outputs (no real inference)
```

---

## Score CSV Schema

Every baseline wrapper must write rows in this format:

```
stream_index,image_path,label,category,anomaly_score,latency_ms,peak_vram_mb,status
```

- `status`: wrapper-status extension — `measured` for real rows, `placeholder_not_measured` for stubs
- `status` is NOT a model output; never use it as an anomaly signal

---

## Baseline Wrapper Contract

```python
# experiments/baselines/<baseline>.py
def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    """Write common score CSV rows or raise RuntimeError if not configured."""
```

Stubs currently raise `RuntimeError` with a clear message. Do not write fake anomaly scores.

---

## Gitignore Policy

| Path | Status |
|---|---|
| `data/**` | Gitignored (real datasets) |
| `data/README.md` | **Tracked** |
| `external/**` | Gitignored (baseline clones) |
| `external/README.md` | **Tracked** |
| `checkpoints/**`, `*.pt`, `*.pth`, `*.ckpt` | Gitignored |
| `results/archive/**` | Gitignored |
| `results/latest/streams/**`, `*.npy`, `*.npz`, `*.pt`, `*.pth` | Gitignored |
| `results/latest/scores.csv`, `manifest.json`, `latest_run.json`, `tables/**`, `figures/**` | **Tracked** |
| `.omx/` | Gitignored (planning history, not source of truth) |

---

## No-Fake-Results Rule

Never place fabricated metrics in `paper/paper.tex`, `paper/paper.md`, `paper/paper.pdf`, or `results/latest/`. Missing or unrun results must remain TODO/placeholder with `paper_allowed: false`.

---

## P0 Scope (Future)

- Datasets: MVTec AD + VisA
- Streams: i.i.d., bursty
- Prevalence: 0.05 | ε: 0, 0.01, 0.05
- Baselines: RareCLIP, PatchCore, WinCLIP, AnomalyCLIP
- Memory policies (RareCLIP/PatchCore): default/SCS, FIFO, Reservoir, Prototype-EMA
- Calibration: none, temperature scaling
- Metrics: Image AUROC, AUPR, ECE, latency, CRD-lite

See `experiments/configs/p0.yaml` and `docs/experiment-prd.md` for details.

---

## Planning Artifacts

`.omx/` contains deep-interview specs, ralplan drafts, and planning documents. These are **planning history only** — not source of truth. This file (`AGENTS.md`) and `docs/experiment-prd.md` are the canonical references for a fresh agent.
