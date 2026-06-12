# ZIAD Protocol — Streaming Industrial Anomaly Detection Evaluation

ZIAD is a **streaming evaluation protocol** for industrial anomaly detection: it
measures how detectors behave when test images arrive as an ordered stream
(i.i.d. vs. bursty), rather than as a static offline benchmark. Its headline
measurement is the **burst-minus-i.i.d. AUROC gap (ΔB-I)**, paired with a
**bank-trace** diagnostic that separates *order-invariant ranking* from
*order-invariant memory* in state-updating detectors.

This is the **full repository** for the project. It contains, as equal first-class
uses:

- the **experiment harness** to reproduce the paper's results from code,
- the **paper source and build** for the manuscript, and
- the **development history** of how the protocol and its evidence were built.

---

## Repository layout

| Path | Contents |
|------|----------|
| `experiments/` | Stream construction, baseline wrappers, runners, summarizers |
| `experiments/baselines/` | PatchCore, WinCLIP, AnomalyCLIP, RareCLIP, OWK, OPCLite wrappers |
| `experiments/configs/` | Run configs (incl. `paper_candidate/` L64 slices) and `baselines.yaml` |
| `scripts/` | Build / render / sweep shell helpers |
| `docs/` | [`reproduction.md`](docs/reproduction.md) (repro map), [`development_pipeline.md`](docs/development_pipeline.md) (dev history), runtime/env notes |
| `results/latest/` | Generated artifacts. Only the 6 paper-referenced tables/figure are tracked; raw runs/streams/scores are gitignored |
| `paper/` | LaTeX source and the built `paper.pdf` |
| `data/`, `external/` | Datasets and baseline clones — **not committed**, placed locally |

---

## Setup

1. **Python** 3.10 and the harness dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   `requirements.txt` records *our* environment versions; see the honesty note
   in that file. In particular `torch==1.13.1+cu116` is CUDA-specific — install
   the torch build matching your platform (the harness falls back to CPU when
   CUDA is unavailable). Baseline-specific deps (torchvision, CLIP, etc.) come
   from each external baseline repo.

2. **Datasets** — MVTec AD and VisA. Download and place them under `data/` as
   described in [`data/README.md`](data/README.md). Real data is never committed.

3. **Baselines** — clone the four upstream repos under `external/` at the pinned
   commits and obtain their checkpoints, as described in
   [`external/README.md`](external/README.md) and
   `experiments/configs/baselines.yaml`.

Setup is shared by both the reproduction path (a) and the paper build (b) below.

---

## (a) Reproducing the experiments

The paper's evidence is regenerated in two stages: **(1) run** the streaming
inference, then **(2) summarize** it into the committed tables/figure. Each
experiment below maps a command to the exact artifact it produces. Full
command sequences (plan generation, per-category/seed steps, expected outputs)
are in **[`docs/reproduction.md`](docs/reproduction.md)**; this is the overview.

### What you regenerate → which paper artifact

| Experiment | Run → Summarize | Paper artifact (`results/latest/…`) |
|---|---|---|
| 4-baseline comparison (MVTec+VisA, L64) | L64 shards via `run_paper_candidate_step.py` → `summarize_paper_candidate_all_datasets.py` | `tables/paper_candidate_baseline_comparison_all_datasets_none.tex` |
| Stream/contamination breakdown | same shards → `summarize_paper_candidate_stream_epsilon.py` | `tables/paper_candidate_stream_epsilon_breakdown_none.tex` |
| Focused-slice bootstrap CIs | `summarize_focused_evaluation_ci.py` | `tables/focused_evaluation_ci_summary.tex` |
| Bank-trace order mechanism | `run_banktrace_gate2.py`, `run_banktrace_visa_gate2.py` → `summarize_order_mechanism.py` | `tables/order_mechanism_summary.tex` |
| Positive controls (OWK / OPCLite) | `run_rareclip_scs_experiments.sh` + L64 control configs → `summarize_online_patchcore_lite_sweep.py` | `tables/online_memory_detector_comparison.tex` |
| Accuracy–latency trade-off | `render_paper_candidate_analysis.py` | `figures/paper_candidate_accuracy_latency_tradeoff.pdf` |

### Supporting probes (referenced in the paper's analysis/limitations)

| Probe | Command |
|---|---|
| Same/cross-category-fill control | `python3 experiments/run_control_gate2.py` → `summarize_concat_control.py` |
| Policy-swap (FIFO/Reservoir memory) | `python3 experiments/run_policyswap_gate.py` → `summarize_policyswap.py` |

> The bank-trace, control, and policy-swap runners are self-contained drivers
> (the gate runners take no required arguments; `run_control_gate2.py` and
> `run_policyswap_gate.py` accept `--gate1` for a 1-cell sanity check). They
> reuse the L64 SCS streams and write under `results/latest/paper_candidate/`.

### Notes on inputs and determinism

- Streams are constructed deterministically (seeded) by
  `experiments/make_streams.py`; given the same code, data, and seed the scores
  and bank-trace centroids are reproducible run-to-run.
- The per-run streams, scores, and execution plans live under `results/latest/`
  and are gitignored (~tens of GB). They are **regenerated**, not shipped — see
  [`docs/reproduction.md`](docs/reproduction.md) for the plan-generation step.

### What's included vs. regenerated

- **Committed:** the 6 paper-referenced artifacts above (5 tables + 1 figure),
  the harness code, configs, and the LaTeX source.
- **Not committed (regenerated locally):** datasets (`data/`), baseline clones
  and checkpoints (`external/`), all per-run streams/scores/metrics/execution
  plans and the internal review gate JSONs under `results/latest/`.

---

## (b) Building the paper

The six tables/figure the paper `\input`s are committed, so the manuscript builds
directly:

```bash
make paper          # or: bash scripts/build_paper.sh
```

This refreshes the tracked tables (a no-op if they are unchanged) and produces
`paper/paper.pdf`. To refresh only the paper-facing tables:

```bash
make paper-tables   # or: bash scripts/render_paper_tables.sh
```

The build works against either the committed tables or tables you regenerated
via path (a).

---

## Development history

The full end-to-end development log — smoke runs, the staged P0 tiers,
mini-matrices, full-category sweeps, and the `paper_allowed` review gates that
governed promotion from pipeline evidence to paper results — is preserved in
[`docs/development_pipeline.md`](docs/development_pipeline.md). It records how the
evidence was built and validated; some of its status lines describe intermediate
states that predate the final paper-candidate runs.

---

## Tests

```bash
python3 -m unittest discover -v
python3 -m compileall experiments tests
```

---

## Citation

This repository accompanies the ZIAD paper (`paper/paper.pdf`). If you use the
protocol or its harness, please cite the paper; baseline detectors retain their
own upstream citations (see `experiments/configs/baselines.yaml`).
