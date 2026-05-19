# AGENTS.md — ZIAD Protocol

Project: **Streaming Zero-Shot Industrial Anomaly Detection with CLIP (CLIP ZSAD)**
Goal: Benchmark CLIP-based anomaly detection baselines under streaming conditions (i.i.d./bursty, prevalence 0.05, configurable contamination ε), publish results as an ACCV/LNCS paper.

Canonical experiment reference: [`docs/experiment-prd.md`](docs/experiment-prd.md)

---

## Current Status

**Setup smoke gate: PASSED** — docs, configs, scripts, and wrapper stubs exist.
**First success gate A: NOT YET** — requires real baseline clone + real dataset.
**Paper gate: NOT YET** — requires real measured results.

All baseline repo URLs and commit hashes are **TBD** — do not fabricate them.

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
      baselines.yaml          # Registry: 4 baselines, all repo_url/commit_hash TBD
      p0.yaml                 # Full P0 matrix (future path, not required for first success)
    baselines/
      base.py                 # BaselineWrapper ABC + _setup_error() helper
      patchcore.py            # PatchCore wrapper stub (raises RuntimeError until cloned)
      rareclip.py             # RareCLIP wrapper stub
      winclip.py              # WinCLIP wrapper stub
      anomalyclip.py          # AnomalyCLIP wrapper stub
    evaluate.py               # Placeholder evaluator
    make_streams.py           # Placeholder stream generator
    prepare_data.py           # Placeholder data prep
    run_baselines.py          # Placeholder baseline runner

  scripts/
    run_smoke.sh              # Smoke runner → results/latest/scores.csv (exits if baseline/data missing)
    setup_baselines.sh        # Prints TBD clone slot instructions (does not clone)
    run_p0.sh                 # Refreshes P0 placeholder outputs (no real inference)
    build_paper.sh            # Builds paper/paper.pdf (or placeholder if no LaTeX)

  data/
    README.md                 # Dataset layout doc (gitignored except this file)
    mvtec_ad/                 # NOT committed — place locally
    visa/                     # NOT committed — place locally

  external/
    README.md                 # Baseline clone layout doc (gitignored except this file)
    RareCLIP/                 # NOT committed — clone locally once URL is pinned
    PatchCore/                # NOT committed — clone locally once URL is pinned
    WinCLIP/                  # NOT committed
    AnomalyCLIP/              # NOT committed

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
1. Pin baseline repo URL/commit in `experiments/configs/baselines.yaml`
2. `git clone <URL> external/<Baseline> && cd external/<Baseline> && git checkout <COMMIT>`
3. Download dataset to `data/mvtec_ad/` (or configured root)
4. Implement `experiments/baselines/<baseline>.py` `run()` method
5. `bash scripts/run_smoke.sh`

### Gate 3: Paper Gate
`manifest.paper_allowed=true` — only after real measured results are produced and reviewed. Placeholder outputs must keep `paper_allowed: false`.

---

## Key Commands

```bash
bash scripts/setup_baselines.sh   # Show TBD clone instructions for all 4 baselines
bash scripts/run_smoke.sh         # Smoke run (fails clearly if baseline/data missing)
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
