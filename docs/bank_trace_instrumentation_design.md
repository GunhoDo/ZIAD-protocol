# RareCLIP/SCS bank-trace instrumentation — design + locked interpretation rules

Status: **DESIGN ONLY — not implemented.** This note exists so the analysis rules
are fixed *before* any data is seen, extending the "separate measurement from claim"
discipline used throughout the CRD-lite/strong-ε honesty pass.

## Hypothesis under test (single)
"SCS rapidly converges the memory bank to an order-invariant fixed point, so RareCLIP
scores behave essentially stateless (hence ΔB-I ≈ 0 despite per-sample memory updates)."

## Approved minimal instrumentation (summary only, no tensor dumps)
Per-step sidecar CSV written once after the loop, read-only, computed AFTER the
latency timer ends (wrapper `experiments/baselines/rareclip.py`, after the
`latency_ms` line in `_predict_rows`). Gated behind a default-off config flag.
Upstream `external/RareCLIP/` is never modified.

Fields per step:
- `stream_index` (int) — align/join (1:1 with upstream `tested_num`)
- `label` (0/1) — locate bursty block boundaries (0→1 transitions)
- `pfm_size` = `PFM[0][0].shape[0]` (int) — convergence: when coreset saturates `sample_num`
- `pfm_centroid_l2_delta` (float) = ‖mean(PFM[0][0])_t − mean(PFM[0][0])_{t−1}‖₂ — core drift signal
- `score_mem_mean_delta` (float) = mean(score_memory)_t − mean(_{t−1}) — secondary (re-scoring stabilization)

Representative index `[ri][l] = [0][0]` (matches the `keep_snum` gate at upstream
line 361); may be extended to mean drift over all `(ri,l)` if `[0][0]` is unrepresentative.

Score-level order-invariance (the hypothesis *consequence*) is measured from the
**existing `scores.csv`** by joining i.i.d. vs bursty on `image_path` — **no instrumentation
needed**. Instrumentation only supplies the *mechanism* (bank convergence). This is the
safety net: even if instrumentation is never built, the score-level test survives.

## LOCKED RULE 1 — interpretation ceiling (necessary, not sufficient)
`pfm_centroid_l2_delta → 0` AND final-step centroid distance between the two orderings ≈ 0
satisfy a **NECESSARY condition** of the hypothesis. They do **NOT** prove the sufficient
condition (the centroid is a lossy summary; identical centroids can hide different
membership). Any claim of an actual order-invariant fixed point requires the
**membership-hash upgrade** (store a hash/sorted-id set of coreset members, not just the
centroid). Until then, wording must stay at "consistent with / necessary condition met",
never "proves convergence". This rule must be reproduced as a comment in the
instrumentation code when it is implemented.

## LOCKED RULE 2 — B-3 bursty-boundary spike threshold (define before seeing data)
Pre-registered decision rule for whether the drift "spikes" at a bursty block entry:
- Baseline = distribution of `pfm_centroid_l2_delta` over i.i.d. steps of the *same*
  (category, seed) run (which has no contiguous anomaly block).
- A bursty block-entry step counts as a **spike** iff its drift exceeds the i.i.d. baseline
  **mean + 3σ** (equivalently, a ≥3σ outlier against the matched i.i.d. drift distribution).
- If this quantitative rule cannot be applied (e.g. too few i.i.d. steps to estimate σ
  stably), B-3 is **downgraded to qualitative observation only, with no strong claim.**
This threshold is fixed now to prevent post-hoc rationalization.

## LOCKED RULE 3 — final-centroid storage exception (explicitly approved)
B-2 cross-ordering comparison needs the final coreset centroid vector ([D]≈768 float, ~6 KB).
This is an **explicit, justified exception** to the "no tensor dumps" rule, approved because
it is required for the order-invariance test. Constraint: store **one vector per run (final
step only)** — never per step. The per-step sidecar stays pure summary scalars.

## Gate-1 finding (1 cell: bottle, seed 0, bursty, eps=0, L64) — run-to-run nondeterminism
The instrumented cell ran in 328.7 s wall-clock (consistent with the ~315 s unit-time
estimate). Its per-image `anomaly_score` differs from the pre-existing non-instrumented
scores.csv for the same stream, but this is **not** an instrumentation effect:
- **Step 0 already differs** (|Δ| = 3.67e-4). At step 0 `tested_num=0`, every bank is empty
  and the score is the text branch only (no memory influence), and the snapshot runs *after*
  score extraction. Neither memory nor instrumentation can act there — so the divergence
  originates in the model **forward pass** (CLIP encode under autocast + multithreaded BLAS
  reduction order + `topk(sorted=False)` in SCS).
- **|Δscore| is uniform numeric-noise scale**: min 4.9e-5, median 1.25e-3, mean 2.78e-3,
  max 3.4e-2 (rel. mean ~0.2%); first-8 mean 7.5e-4 → last-8 2.2e-3 (compounds via the bank
  path but stays bounded at ~1e-3). A logic change would not look like this.

Instrumentation no-impact therefore stands on the structural argument: `_bank_trace_step`
runs after the latency timer and score extraction, reads only detached copies
(`detach().float().mean().cpu()`), calls no model method, mutates nothing, and consumes no
RNG. The score difference vs the old file is just "a different run."

**MAIN-TEXT PROMOTION CANDIDATE.** This is a methodological finding about ΔB-I estimator
reliability, not just an instrumentation detail: the ΔB-I / order-effect axis has a
**run-to-run resolution floor (~1e-3)** below which differences are model nondeterminism,
not stream order. It is a candidate for the paper's main text (e.g. a reproducibility caveat
on ΔB-I, or a sentence in the positive-controls / statistical-uncertainty discussion).
Decision deferred until Gate-2 data quantifies the floor; flagged here so it is not lost.

## LOCKED RULE 4 — nondeterminism noise floor (Gate-2 design refinement)
> **[CORRECTED BY GATE-2 — see "GATE-2 RESULTS & CORRECTIONS" below.]** The premise here
> (run-to-run nondeterminism) is wrong: the floor turned out to be exactly zero (RareCLIP is
> deterministic in a fixed environment). The repeat-baseline *method* was still correct — it
> is what proved the floor is zero. Keep the rule as the methodology; ignore the "~1e-3" value.

RareCLIP is **not run-to-run reproducible** (~1e-3 score level, proportional feature jitter).
Any i.i.d.-vs-bursty difference in bank trajectory / final-centroid distance must therefore
be shown to **exceed the model's own run-to-run noise floor**, or it cannot be attributed to
stream order. Gate 2 must add, per (category, seed), a **same-ordering repeat run** whose
trajectory/centroid difference defines that noise floor. This composes with Rule 2: the B-3
spike threshold and any order-effect claim are evaluated *against the repeat-run floor*, not
against zero. Strong Gate-1 signals already clear this floor by 1–2 orders of magnitude
(convergence envelope 6.8× decay; first-burst spike 0.193 vs Rule-2 mean+3σ 0.0248); the
weak late-boundary bumps (0.002–0.02) sit near the floor and are undecidable without it.

## LOCKED RULE 5 — repeat-floor decision rule (pre-registered, before Gate-2 data)
Quantitative acceptance rule for "stream order moved the bank", fixed before any Gate-2
numbers are seen. Primary statistic = final-step PFM[0][0] centroid L2 distance.
- **Noise floor** `d_rep`: per (category, seed), run the bursty stream twice (identical
  ordering); `d_rep` = L2 distance between the two repeats' final centroids. Across the
  slice this yields a distribution (mean μ_rep, sd σ_rep).
- **Order statistic** `d_ord`: per (category, seed), L2 distance between the i.i.d. and
  bursty final centroids (same image multiset, different order).
- **ACCEPT an order effect** iff BOTH hold at the slice level:
  (i) mean(`d_ord`) > μ_rep + 3·σ_rep, AND
  (ii) a paired Wilcoxon signed-rank of `d_ord` > `d_rep` across cells rejects at p < 0.05.
  A single-cell effect is "accepted" iff `d_ord` ≥ 3·`d_rep` for that matched (cat, seed).
- **B-3 boundary bumps** (per-step drift): the Gate-1 within-run label==0 baseline is
  replaced by the same-order repeat drift distribution at the matched step; a 0→1 boundary
  is a spike iff its drift exceeds repeat mean+3σ at that step.
- **Insufficiency fallback**: if fewer than ~10 usable `d_rep` pairs (so σ_rep is unstable),
  the WEAK-signal region (late-boundary bumps) is downgraded to **qualitative observation
  only, no strong claim**; the strong signals (convergence envelope, first-burst spike) are
  still reported quantitatively because they clear any plausible floor by 1–2 orders.
- **Rule 1 still binds**: even a fully accepted order effect with d→0 convergence is only the
  NECESSARY condition; sufficiency needs the membership-hash upgrade.

## GATE-2 RESULTS & CORRECTIONS
Slice: MVTec AD {bottle, cable, capsule} × seeds 0–9, ε=0, L=64, default/SCS. 90 cells
(89 run + the Gate-1 seed) = per (cat,seed): iid, bursty, bursty-repeat. Run 6.96 h, serial.

### Verification — in-environment determinism (corrects the Gate-1 nondeterminism claim)
Decisive re-check, two independent methods, over all 30 (cat,seed) bursty-vs-bursty_repeat
pairs: the `anomaly_score` column is **bit-identical** — **0 / 1920** per-row string
mismatches, and a raw byte `diff` on the score column = IDENTICAL. Only `latency_ms` differs
(30/30 pairs), which is why an earlier whole-file `diff -q` reported DIFFER. The PFM[0][0]
final centroid is identical too: **d_rep = 0.000 exactly, all 30 pairs**.
⇒ RareCLIP is **fully deterministic run-to-run in a fixed environment** (score AND memory).
The Gate-1 ~1e-3 difference was against a PRE-EXISTING file from a different environment/code
version (a cross-environment artifact), **not** run-to-run nondeterminism. This **supersedes**
the Gate-1 "resolution floor (~1e-3)" line and the premise of Rule 4.

### Rule-5 verdict — order DOES move the memory (deterministically)
d_rep = 0.000 (all 30). d_ord (iid vs bursty final centroid) = mean 0.0108, range
[0.0072, 0.0135]. (i) 0.0108 > μ_rep+3σ_rep = 0 ✓; (ii) paired Wilcoxon p = 9.3e-10 ✓;
single-cell d_ord ≥ 3·d_rep = 30/30. ⇒ **ACCEPT order effect.** The SCS coreset is
**order-sensitive**, not an order-invariant fixed point.

### Signal verdicts (Gate-1 framing)
- STRONG (convergence envelope): within-run drift first-third 0.0212 → last-third 0.0030,
  decay 6.9× (30/30); first-burst spike mean 0.027. ⇒ rapid convergence CONFIRMED — but to an
  order-DEPENDENT state.
- WEAK (late per-step boundary bumps): 0/162 exceed the repeat steady-state floor (0.0373).
  ⇒ NEGATIVE, now decidable with full pairing.

### Score & ranking level (B-4, full pairing)
- Same image, iid vs bursty: per-image score differs by mean **0.030** (30/30, p=9e-10, vs a
  zero floor) ⇒ scores are **NOT stateless**; order changes individual scores.
- Yet AUROC iid 0.9857 vs bursty 0.9835; **ΔB-I = −0.0022** (median|·| 0.0031, Wilcoxon
  p=0.72, 20/30 within ±0.01) ⇒ discrimination invariant. (Matches the paper's RareCLIP ΔB-I≈0.)

### Mechanism verdict — original hypothesis FALSIFIED; refined mechanism
"SCS → order-invariant fixed point → stateless scores → ΔB-I=0" is false in **both** clauses:
the fixed point is order-dependent (d_ord≫0) and scores are order-sensitive (0.030/image).
Supported mechanism: **SCS yields order-sensitive memory and order-sensitive per-image scores,
but the perturbation is RANK-PRESERVING, so AUROC (hence ΔB-I) is invariant.** "ΔB-I=0 despite
per-sample memory updates" is explained by order-invariant **ranking**, not order-invariant
memory. Rule 1 vindicated: within-run drift decay alone would have wrongly implied an invariant
fixed point; the pre-registered cross-order centroid test disproved invariance.
