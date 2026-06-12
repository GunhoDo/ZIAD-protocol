# Reproduction Guide

This document expands the repro map in the top-level [`README.md`](../README.md)
into concrete command sequences for regenerating the paper's six committed
artifacts and the supporting probes. It assumes **Setup** (datasets under
`data/`, baselines under `external/`, `pip install -r requirements.txt`) is done.

All commands are run from the repository root. Per-run streams, scores, and
execution plans are written under `results/latest/` and are gitignored; only the
final tables/figure are tracked.

---

## Committed artifacts and their generators

| # | Artifact (`results/latest/…`) | Generator |
|---|---|---|
| 1 | `tables/paper_candidate_baseline_comparison_all_datasets_none.tex` | `summarize_paper_candidate_all_datasets.py` |
| 2 | `tables/paper_candidate_stream_epsilon_breakdown_none.tex` | `summarize_paper_candidate_stream_epsilon.py` |
| 3 | `tables/focused_evaluation_ci_summary.tex` | `summarize_focused_evaluation_ci.py` |
| 4 | `tables/order_mechanism_summary.tex` | `summarize_order_mechanism.py` |
| 5 | `tables/online_memory_detector_comparison.tex` | `summarize_online_patchcore_lite_sweep.py` |
| 6 | `figures/paper_candidate_accuracy_latency_tradeoff.pdf` | `render_paper_candidate_analysis.py` |

A summarizer reads the inference outputs of a prior **run** stage. The two
stages are described below.

---

## Stage 0 — streams and execution plans

Streams are constructed deterministically (seeded) by
`experiments/make_streams.py`. The paper-candidate experiments are driven by
per-experiment **execution plans** generated from the configs under
`experiments/configs/paper_candidate/`:

- `rareclip_scs_delta_bi_sl64.yaml` — MVTec AD focused ΔB-I slice, L64
- `rareclip_scs_delta_bi_visa_pcb_sl64.yaml` / `..._sl256.yaml` — VisA pcb slice (power-resolved at L64/L256)
- `online_window_knn_sl64.yaml`, `online_patchcore_lite_k8_sl64.yaml`, `opc_visa_pcb_sl64.yaml` — positive controls (OWK / OPCLite)

The planning entry point is `experiments/paper_candidate.py` (it writes a
restartable `execution_plan.json`). The worked end-to-end driver for the VisA
power-resolved RareCLIP + OPCLite slice is committed as
[`run_rareclip_scs_experiments.sh`](../run_rareclip_scs_experiments.sh); read it
as the canonical example of the plan → step → category loop.

---

## Stage 1 — run, then summarize

### Artifacts 1, 2, 6 — 4-baseline comparison, stream/ε breakdown, trade-off figure

**Run** the L64 shards for the four baselines across MVTec AD (15 categories)
and VisA (12 categories), seeds, `iid`/`bursty`, ε `0`/`0.05`, via the
execution plan:

```bash
python3 experiments/run_paper_candidate_step.py \
  --plan results/latest/paper_candidate/<experiment>/execution_plan.json \
  --step-id <dataset>:<baseline>:<memory_policy>:none \
  --category <category>
```

(One invocation per step/category; the runner is resumable and skips completed
shards. See `run_rareclip_scs_experiments.sh` for the loop structure.)

**Summarize:**

```bash
python3 experiments/summarize_paper_candidate_all_datasets.py     # -> artifact 1
python3 experiments/summarize_paper_candidate_stream_epsilon.py   # -> artifact 2
python3 experiments/render_paper_candidate_analysis.py            # -> artifact 6 (+ ranking table)
```

### Artifact 3 — focused-slice bootstrap CIs

```bash
python3 experiments/summarize_focused_evaluation_ci.py            # -> artifact 3
```

This computes stratified bootstrap intervals over the focused MVTec/VisA slice
from the same category-shard metrics; it runs no new inference.

### Artifact 4 — bank-trace order mechanism

The bank-trace runners are **self-contained** (no required arguments). They
reuse the L64 SCS streams, run RareCLIP with the read-only bank-trace
diagnostic, and write per-step bank traces:

```bash
python3 experiments/run_banktrace_gate2.py          # MVTec slice
python3 experiments/run_banktrace_visa_gate2.py     # VisA slice
python3 experiments/run_banktrace_concat_gate2.py   # concat/category-boundary slice
python3 experiments/summarize_order_mechanism.py    # -> artifact 4
```

### Artifact 5 — positive controls (OWK / OPCLite)

Run the OWK / OPCLite controls (the VisA pcb power-resolved slice is driven by
the committed script), then summarize:

```bash
bash run_rareclip_scs_experiments.sh                        # OPCLite + RareCLIP, VisA pcb, L64 & L256
python3 experiments/summarize_online_patchcore_lite_sweep.py   # -> artifact 5
```

---

## Supporting probes

These back the paper's analysis and limitations but are not among the six
committed tables (their detailed figures live in the gitignored generated
artifacts under `results/latest/paper_candidate/`).

```bash
# Same / cross-category-fill control
python3 experiments/run_control_gate2.py            # add --gate1 for a 1-cell sanity check
python3 experiments/summarize_concat_control.py

# Policy-swap probe (FIFO / Reservoir memory policies)
python3 experiments/run_policyswap_gate.py          # add --gate1 for a 1-cell sanity check
python3 experiments/summarize_policyswap.py
```

`run_policyswap_gate.py` reuses the MVTec bottle/cable/capsule L64 SCS streams
and swaps only the memory policy; the scoring code path is unchanged (scores
differ by policy design). See Limitation 2 in the paper.

---

## Verifying the regeneration

The six artifacts are committed, so you can diff your regenerated tables/figure
against the tracked versions:

```bash
git status --short results/latest/tables results/latest/figures
git diff -- results/latest/tables
```

Numeric tables should match up to floating-point/bootstrap-seed tolerance.

To rebuild the manuscript from the (regenerated or committed) tables/figure:

```bash
make paper          # or: bash scripts/build_paper.sh  -> paper/paper.pdf
```

---

## Determinism

Given identical code, data, seed, and libraries, the per-image anomaly scores
and the bank-trace memory centroids are reproducible run-to-run (the bank-trace
gate verifies a bit-identical same-order repeat). Reservoir-based policies are
reproducible via a fixed `reservoir_seed`. Hardware/library differences (BLAS,
torch/CUDA build) can introduce small floating-point deltas; the bootstrap CIs
absorb these at the reported precision.

For the recorded runtime environment (CPU, OS, exact library versions used for
our runs) see [`runtime_environment.md`](runtime_environment.md).
