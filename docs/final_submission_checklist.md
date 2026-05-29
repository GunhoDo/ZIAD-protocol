# Final Submission Checklist

Status as of 2026-05-29: the manuscript is submission-ready for the compact
ZIAD evaluation slice under conservative repository governance. The automated
promotion report is still blocked from changing repository result gates because
manual reviewer approval has not been recorded. No metadata gate is changed by
this checklist.

## Completed Automated Checks

- Combined baseline table exists:
  `results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv`
- Combined table covers 2 datasets and 4 baselines:
  MVTec AD and VisA; PatchCore, WinCLIP, AnomalyCLIP, RareCLIP.
- Combined table row count is 8.
- Per-baseline row/category contracts match:
  MVTec AD has 15 categories and 180 rows per baseline; VisA has 12 categories
  and 144 rows per baseline.
- Stream/epsilon breakdown exists:
  `results/latest/paper_candidate/stream_epsilon_breakdown_none.csv`
- Stream/epsilon breakdown has 32 groups:
  2 datasets x 4 baselines x 2 stream types x 2 epsilon values.
- Accuracy-latency figure exists:
  `results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png`
- Ranking summary exists:
  `results/latest/paper_candidate/baseline_ranking_summary.json`
- Metric audit passes with no missing, NaN/Inf, or negative-latency values.
- Paper source contains no submission-blocking markers:
  `TODO`, `pending final audit`, `candidate-stage`, `paper_allowed`,
  `claim_allowed`, `state of the art`, or `SOTA`.
- The manuscript states latency semantics as local-runtime dependent.
- The manuscript states the stream-length limitation honestly.
- The manuscript does not make unsupported calibration, memory-policy,
  broad stream-length robustness, or state-of-the-art claims.
- ACCV/LNCS template readiness passes.
- ACCV PDF build succeeds.

## Gate Decision

- Keep repository metadata conservative:
  `paper_allowed=false`, `claim_allowed=false`, and
  `review_status=review_pending`.
- Rationale: the manuscript can use the audited compact evaluation slice for
  submission-facing analysis, while repository-level claim promotion still
  requires explicit manual reviewer approval.

## Remaining Non-Blocking Limitations

- The main evaluation is compact: stream length 64, calibration `none`, and the
  documented baseline memory settings.
- Latency is a local-runtime comparison, not a device-independent hardware
  benchmark.
- The stream-length sanity check is intentionally tiny:
  MVTec AD bottle with WinCLIP at lengths 64, 128, and 256.
- Future protocol axes such as richer memory policies, calibration variants,
  prevalence sweeps, drift, additional datasets, and statistical uncertainty
  remain outside the compact evidence slice.

## Final Submission Risks

- Reviewers may ask for broader stream-length or drift coverage.
- Reviewers may ask for stronger timing controls or hardware-normalized latency.
- Reviewers may treat the contribution as benchmark engineering unless the
  protocol formalization and stream/epsilon breakdown remain prominent.
- Reviewers may ask for calibration and memory-policy ablations; the manuscript
  currently frames those as protocol extensions rather than completed claims.
