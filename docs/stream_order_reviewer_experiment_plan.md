# Stream-Order Reviewer Experiment Plan

This note tracks the experiments needed to answer the reviewer concern that the
ZIAD protocol must demonstrate a measurable stream-order effect, not merely
report near-zero deltas for frozen image-level detectors.

## Current Evidence Status

| Evidence item | Status | What it shows | Limitation |
|---|---:|---|---|
| Main frozen baselines | Complete | PatchCore, WinCLIP, AnomalyCLIP, and RareCLIP are effectively stream-order invariant under matched i.i.d./bursty streams. | This confirms expected offline behavior but does not prove a real online detector changes with order. |
| OrderSensitiveToy | Complete | A diagnostic toy probe has non-zero point estimates: MVTec AD `+0.006`, VisA `+0.030`. | Bootstrap 95% CIs include zero, so it is a weak positive control only. |
| OnlineWindow post-hoc wrapper | Complete as diagnostic | Applying a sliding-window score wrapper to frozen scores gives significant non-zero Delta B-I in 3/8 dataset-baseline cells. | It is post-hoc score adaptation, not a real detector with an updating memory bank or threshold. |
| Strong epsilon diagnostic | Partial | VisA AnomalyCLIP completed 6 categories at epsilon `{0,0.05,0.1,0.2}` and exposes AUROC/AUPR term interactions. | Not all categories, not all baselines, and not a main claim. |
| True online detector | Success criterion met | OnlineWindowKNN completed a 3-category MVTec AD pilot with a FIFO memory bank updated after every stream observation and 60 category/seed/epsilon strata. | The detector is a lightweight diagnostic, not a leaderboard baseline; requested stream length 256 was clamped by no-duplicate category pools. |

## Priority 1: True Online Detector

Goal: integrate one detector whose state changes during stream processing and
measure Delta B-I with bootstrap CIs.

Completed first pilot:

| Choice | Value |
|---|---|
| Dataset | MVTec AD |
| Detector | OnlinePrototypeEMA |
| Categories | bottle, cable, capsule |
| Stream length | requested 128; bottle was clamped by the no-duplicate image pool |
| Seeds | 0, 1, 2, 3, 4 |
| Streams | i.i.d., bursty |
| Epsilon | 0, 0.05 |
| Metric rows | 60 |
| Bootstrap unit | category/seed/epsilon stratum |
| Delta B-I | `+0.003971` |
| 95% CI | `[-0.008195,+0.015609]` |
| Success criterion | Not met; CI includes zero |

Output artifacts:

- `results/latest/paper_candidate/diagnostic_online_prototype_ema/online_memory_delta_bi_summary.csv`
- `results/latest/paper_candidate/diagnostic_online_prototype_ema/online_memory_delta_bi_summary.json`
- `results/latest/tables/online_prototype_ema_delta_bi.tex`

Completed stronger pilot:

| Choice | Value |
|---|---|
| Dataset | MVTec AD |
| Detector | OnlineWindowKNN |
| Memory update | FIFO nearest-neighbor memory bank, updated after every observation |
| Categories | bottle, cable, capsule |
| Stream length | requested 256; clamped by no-duplicate pools to bottle 83, cable 150, capsule 132 |
| Seeds | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 |
| Streams | i.i.d., bursty |
| Epsilon | 0, 0.05 |
| Metric rows | 120 |
| Bootstrap unit | category/seed/epsilon stratum |
| Bootstrap samples | 5000 |
| Strata | 60 |
| Delta B-I | `+0.013522` |
| 95% CI | `[+0.005100,+0.021573]` |
| Empirical SE | `0.004214` |
| MDE95 | `0.008259` |
| Success criterion | Met; CI excludes zero |

Output artifacts:

- `results/latest/paper_candidate/diagnostic_online_window_knn/online_memory_delta_bi_summary.csv`
- `results/latest/paper_candidate/diagnostic_online_window_knn/online_memory_delta_bi_summary.json`
- `results/latest/tables/online_window_knn_delta_bi.tex`

Analytical order-sensitivity check: OnlineWindowKNN scores item \(t\) before
insertion using nearest-neighbor distance to the current FIFO memory bank. That
bank contains the previous stream prefix after FIFO eviction. Therefore
\(\mathrm{score}_t\) depends on memory state, memory state depends on previous
stream items, and changing i.i.d. versus bursty order changes future scores.

RareCLIP Reservoir was also attempted as a more realistic memory diagnostic.
The GPU path is available only outside the default sandbox; under GPU execution
the first tiny smoke shard still did not produce a first metrics row within the
short pilot budget, so partial outputs were moved under
`/tmp/ziad_partial_online_memory/` and the run was not used as evidence.

Recommended next slice if this line remains important:

| Choice | Value |
|---|---|
| Dataset | MVTec AD |
| Detector | PatchCore with FIFO or Reservoir memory bank, or RareCLIP online memory if wrapper support is cleaner |
| Categories | bottle, cable, capsule first; expand to all 15 only if the pilot CI is promising |
| Stream length | 128 |
| Seeds | 5 initially; increase to 10 if CI still includes zero |
| Streams | i.i.d., bursty |
| Epsilon | 0, 0.05 |
| Metrics | AUROC, AUPR, ECE, latency, CRD-lite, Delta B-I |
| Bootstrap unit | category/seed stratum |

Estimated metric rows:

- Pilot: `3 categories x 5 seeds x 2 streams x 2 eps = 60` metric rows.
- Stronger pilot: `3 x 10 x 2 x 2 = 120` metric rows.
- Full MVTec online slice: `15 x 10 x 2 x 2 = 600` metric rows.

Success criterion: the online detector's Delta B-I 95% CI excludes zero.
OnlinePrototypeEMA did not meet this criterion, but OnlineWindowKNN did. This
supports the reviewer-facing conclusion that ZIAD can surface stream-order
sensitivity in a true-online stateful detector while the original frozen
baselines remain order invariant.

Reviewer concern addressed: protocol non-triviality and real stream-order
sensitivity.

## Priority 2: Positive Control Power

Goal: strengthen the diagnostic control without pretending it is a deployable
detector.

Recommended slice:

| Choice | Value |
|---|---|
| Probe | OrderSensitiveToy or OnlineWindow |
| Config sweep | stronger previous-score mixing, window `{8,16,32}`, alpha `{0.1,0.3,0.5}` |
| Datasets | MVTec AD and VisA |
| Categories | all categories if no inference is needed; otherwise 3-category pilot |
| Stream length | 128, 256 |
| Seeds | 5 to 10 |

Current power estimate from OrderSensitiveToy:

- MVTec AD: current point `+0.006`, CI half-width about `0.021` with 45 strata.
  A non-zero claim at this effect size would need roughly `(0.021/0.006)^2`,
  or about 12 times more strata, assuming similar variance.
- VisA: current point `+0.030`, CI half-width about `0.034` with 36 strata.
  A similar effect likely needs about `(0.034/0.030)^2`, or about 1.3 times
  more strata, but category variance may dominate.

Reviewer concern addressed: weak positive control and insufficient statistical
power.

## Priority 3: Latency Confound Control

Goal: prevent latency from being read as a cross-hardware or cross-wrapper
systems benchmark.

Recommended action:

1. Keep latency wording as local-runtime relative comparison unless the whole
   slice is rerun under a controlled device path.
2. If GPU timing is available, rerun a small matched slice on a single GPU with
   identical model-loading scope and batching policy.
3. Add a PatchCore latency decomposition table:
   `dataset`, `category_count`, `memory_bank_size`, `mean_image_count`,
   `mean_latency_ms`, and `notes`.

Estimated rows for a controlled timing pilot:

- `2 datasets x 4 baselines x 3 categories x 3 seeds x 2 streams x 2 eps = 288`
  metric rows, plus timing metadata.

Reviewer concern addressed: latency confounds and unexplained dataset-level
latency gaps.

## Priority 4: Main Slice Extension

Goal: show that ZIAD also distinguishes calibration and stronger contamination.

Recommended minimal extension:

| Axis | Minimal plan |
|---|---|
| Calibration | Promote temperature scaling for one baseline pair first: WinCLIP and PatchCore on MVTec AD, 3 categories, seeds 5. |
| Strong epsilon | Complete VisA AnomalyCLIP strong-epsilon categories, then decide whether to expand to one additional baseline. |

Estimated metric rows:

- Calibration pilot: `2 baselines x 3 categories x 5 seeds x 2 streams x 2 eps x 2 calibrations = 240`.
- Full strong-epsilon VisA AnomalyCLIP: `12 categories x 3 seeds x 2 streams x 4 eps = 288`; current completed subset has 6 categories and 144 rows.

Reviewer concern addressed: calibration axis evidence and CRD-lite ambiguity
under weak contamination.

## Execution Order

1. The first true online detector pilot is complete but does not exclude zero.
2. Do not add the OnlinePrototypeEMA pilot as a positive paper claim.
3. Strengthen OnlineWindow/OrderSensitiveToy power and frame the
   paper as proving the protocol can surface order sensitivity via controlled
   post-hoc adaptation, while real online detector evidence remains future work.
4. Only after stream-order evidence is resolved, decide whether calibration or
   strong epsilon is worth promoting into the main paper.
