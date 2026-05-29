# Targeted Extra Runs Plan

This note defines small follow-up runs that can address reviewer concerns
without reopening the full ZIAD matrix. These runs are not required by the
current focused evaluation unless the uncertainty audit or reviewer feedback
specifically asks for them.

## Current Decision

After visual polish and the no-inference bootstrap audit, no additional
experiment is required before submitting the focused evaluation paper. The
current paper already reports two datasets, four representative baselines,
i.i.d. and bursty streams, epsilon `0` and `0.05`, calibration `none`, latency,
ECE, CRD-lite, and a tiny stream-length sanity check.

## Optional Targeted Slice A: Stream Length 512

Purpose: test whether the stream-length limitation needs one more concrete
sanity point.

Scope:
- Dataset: MVTec AD
- Baselines: WinCLIP, PatchCore
- Categories: bottle, cable
- Stream length: 512
- Streams: iid, bursty
- Epsilon: 0, 0.05
- Seeds: 0, 1, 2
- Calibration: none

Estimated wrapper-timing cost from current local mean latency:
- WinCLIP: roughly 4.6 hours for 12,288 streamed images
- PatchCore: roughly 2.2 hours for 12,288 streamed images
- Total: roughly 6.8 hours plus dataset, model, and Python overhead

Decision: not needed for the current submission unless stream-length robustness
becomes the dominant reviewer risk.

## Optional Targeted Slice B: Calibration Sanity

Purpose: test whether a minimal calibration comparison changes the main
calibration interpretation.

Scope:
- Dataset: MVTec AD
- Baseline: WinCLIP or PatchCore
- Categories: bottle, cable
- Calibration: none versus temperature_scaling
- Stream length: 64
- Streams: iid, bursty
- Epsilon: 0, 0.05
- Seeds: 0, 1, 2

Estimated wrapper-timing cost from current local mean latency:
- WinCLIP-only: roughly 1.1 hours for 3,072 streamed images
- PatchCore-only: roughly 0.6 hours for 3,072 streamed images
- Both baselines: roughly 1.7 hours plus calibration and orchestration overhead

Decision: optional. It is useful only if the paper needs a small empirical
anchor for calibration beyond the existing ECE reporting and limitations.
