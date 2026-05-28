# Paper-Candidate Promotion Checklist

This checklist defines the required review before any ZIAD paper-candidate
artifact can be promoted to a final paper claim. It is intentionally separate
from execution. Running experiments or generating candidate tables is not
enough to open the paper or claim gates.

Do not change `paper_allowed` or `claim_allowed` during this checklist. A
promotion decision must be a separate reviewed step.

## Required artifacts

- Combined candidate table exists:
  `results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv`
- Combined candidate JSON exists:
  `results/latest/paper_candidate/baseline_comparison_all_datasets_none.json`
- Paper table exists:
  `results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex`
- Ranking summary exists:
  `results/latest/paper_candidate/baseline_ranking_summary.json`
- Ranking table exists:
  `results/latest/tables/paper_candidate_ranking_summary.tex`
- Accuracy-latency figure exists:
  `results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png`
- Metric audit report exists:
  `results/latest/paper_candidate/metric_audit_report.json`

## Metric and coverage checks

- Metric audit status is passing.
- Combined table has exactly two datasets: MVTec AD and VisA.
- Each dataset has exactly four baselines: PatchCore, WinCLIP, AnomalyCLIP,
  and RareCLIP.
- Combined table has exactly eight rows.
- Category summaries are complete for every dataset/baseline pair.
- MVTec AD rows cover 15 categories and 180 metric rows per baseline.
- VisA rows cover 12 categories and 144 metric rows per baseline.
- No missing, NaN, Inf, or non-numeric metric values are present.
- No negative latency values are present.
- All candidate rows still have closed gates before promotion review:
  `paper_allowed=false`, `claim_allowed=false`, and
  `review_status=review_pending`.

## Provenance and configuration checks

- Baseline provenance is verified in `experiments/configs/baselines.yaml`.
- Every baseline has a recorded `repo_url` and pinned `commit_hash`.
- PatchCore paper-candidate sampler setting is documented.
- Stream length is documented as `64`.
- Seeds are documented as `0,1,2`.
- Calibration scope is documented as `none` for the main candidate table.
- Memory-policy scope is documented:
  - PatchCore and RareCLIP: default/SCS
  - WinCLIP and AnomalyCLIP: default/no-memory

## Paper and submission checks

- Runtime and timing semantics are documented in `docs/runtime_environment.md`.
- Runtime TODOs are resolved before latency is claimed as final.
- The paper text does not overclaim beyond candidate evidence.
- Limitations mention stream length `64`.
- Limitations mention local-runtime latency caveats.
- ACCV/LNCS template migration status is known.
- The official template migration is complete before final submission-format
  review, or explicitly deferred with venue-compatible justification.
- Manual reviewer approval is recorded.

## Current expected status

The current repository is expected to fail final promotion readiness because
runtime timing semantics and manual reviewer approval are not complete. This
is correct. The readiness report should keep `ready_for_promotion=false` until
those blockers are resolved in a separate reviewed promotion step.

Generate the current readiness report with:

```bash
python3 scripts/check_paper_promotion_readiness.py
```
