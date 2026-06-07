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

## LOCKED RULE 6 — VisA replication, rank-preservation conditional (pre-registered, before VisA data)
Second-dataset replication on VisA {candle, macaroni1, macaroni2} (normal=100,
length-64 floor=0; PCB excluded because its positive control is non-significant;
small-pool categories cashew/chewinggum/fryum/pipe_fryum excluded). Path (A):
mechanism only, **no positive control** is run on these non-PCB VisA categories.
Pre-registered acceptance, fixed before any VisA number is seen:
- **If d_ord >= 3x the same-order floor d_rep** (MVTec-grade order perturbation):
  the bank-trace itself proves stream order perturbs the SCS memory, so the
  rank-preservation claim (order-sensitive memory/scores, invariant AUROC) holds
  **without** a positive control. The paper must then state explicitly that
  VisA non-PCB has no positive control and that the bank-trace directly
  demonstrates the order perturbation.
- **If d_ord ~ d_rep** (order perturbation weak): **do NOT claim rank-preservation.**
  Report honestly that order perturbation is itself weak on this VisA slice, and
  record the positive-control absence as a limitation.
Rationale for path (A): the bank-trace replaces the positive control's role
(estimator detectability) by measuring order perturbation independently of the
ΔB-I estimator --- but the substitution is valid only when that perturbation is
actually strong (first branch). Same-environment determinism (d_rep=0) is
required and re-checked per Rule 4/5; Rule 1 (necessary != sufficient) still
binds. VisA outputs use a SEPARATE directory and their own gate JSON
(paper_allowed=false until author sign-off); flags are never auto-flipped.

## LOCKED RULE 7 — multi-category concatenation: rank-preservation under distribution shift (pre-registered, before data)
Concatenation is a STRESS-TEST of the Rule-6 / sec:order-mechanism rank-preservation
claim under a harder ordering: category boundaries = distribution shift. It is
absorbed into sec:order-mechanism (NO new section, NO new contribution bullet); the
longer streams it enables are reported only as a partial resolution of Limitation 1
("length bound"), never as a new "long-stream" or "distribution-shift measurement"
capability. Paper wording uses "3 cyclic permutations" exactly; never "all permutations".

Design (VisA candle/macaroni1/macaroni2, default SCS, eps=0, prevalence 0.05,
per-block ~105 so concatenated length ~315 > the 201 cap; within-block iid):
- **3 cyclic permutations** [A,B,C],[B,C,A],[C,A,B] place each category once in each
  position (1/2/3). 5 seeds first (30 cells = 3 perm x 5 seed x {base, same-order
  repeat}); extend to 10 seeds (60 cells) ONLY if the 5-seed position signal sits near
  the noise floor (power decision deferred, not pre-committed).

Verdict statistic = **within-category AUROC** (per-block, block items only), which removes
the cross-category score-mean confound. Whole-mixed AUROC is reported as context only
(confounded) and is NOT used for the verdict.

Floor caveat: the same-order repeat AUROC floor is **0** (runs are deterministic, d_rep=0),
so "3x floor" cannot use the repeat floor directly. The operative floor is the
**sec:order-mechanism within-category rank-preservation tolerance** = the §5.4 VisA
single-category **median |ΔB-I|**, taken from the VisA gate JSON field
`summary_stats.delta_b_i.median_abs` = **0.01093** (the sign-cancellation-free absolute
median; NOT the mean, 0.0013). MVTec analog = 0.0031. VisA is used because concatenation
is on VisA. 3x floor ≈ **0.033**.

Pre-registered decision, fixed before any concatenation number is seen. Position-Δ =
within-category AUROC(category at a later position) − within-category AUROC(same category
at first position), over 3 categories x 5 seeds. Criterion is **effect size FIRST,
significance SECOND (tiered, not AND)**:
- **PRIMARY (effect size)**: mean |position-Δ| clearly ≤ 3x floor (≈0.033) → **(A) robust**;
  clearly > 0.033 → **(B) stationarity-conditional**.
- **SECONDARY (only if mean |position-Δ| is in the ambiguous zone around 0.033)**: a paired
  test of position-Δ vs the §5.4 within-category |ΔB-I| baseline (is the shift materially
  LARGER than ordinary within-category order variation?) breaks the tie.
- **If still ambiguous**: extend to seeds 0-9 to resolve; do not force a verdict.
- **Statistical-zero is NOT a criterion**: the single-category baseline is itself 0.011 != 0,
  so "distinguishable from zero" is meaningless here; we test "materially larger than the
  established within-category tolerance", never "different from zero".

(A) → sec:order-mechanism extended to "robust across category-boundary distribution shift
in length-~315 concatenated streams"; abstract obs4 + Limitation 1 updated accordingly.
(B, SHARPENING not a weakness) → claim refined to "holds within a stationary stream; under
category-boundary distribution shift the ranking shifts" --- a more precise, more on-theme
statement of when/what a single metric hides. Folded into sec:order-mechanism as a
conditional; Limitation 1 length addressed but reveals the boundary effect.
- **Boundary memory signal (common to A and B)**: the centroid drift
  `pfm_centroid_l2_delta` is expected to SPIKE in a ±k window at each category boundary
  (memory responds to distribution shift). This is the mix-IMMUNE memory-perturbation
  signal; it does NOT decide A vs B. A = memory spikes + ranking preserved;
  B = memory spikes + ranking shifts.
Same environment pin (acb7481; scoring path unchanged), d_rep=0 re-checked per Rule 4/5;
Rule 1 still binds. Gate JSON paper_allowed=false until sign-off; flags never auto-flipped.

## LOCKED RULE 8 — concat collapse: causal control + aggregate reporting (pre-registered, before Part-B data)
The concat within-category AUROC collapse (Rule 7, scenario B) is reported and tested as
follows; fixed before the Part-B control runs.

Reporting (Part A, applied):
- The collapse is quantified ONLY at the aggregate level: mean position-Δ ≈ 0.20
  (95% CI [0.14, 0.26], bootstrap over the 15 category/seed cells; 14/15 positive). The
  single-cell example (candle 0.96→0.60) is removed from the abstract, Fig 1, and §5.2.
- Per-cell precision is stated proactively as limited: 5 anomalies/block → wide bootstrap
  CIs; only 8/15 paired-position CIs exclude zero; collapse claimed at aggregate, not per cell.

Causal control (Part B): same-category-fill. Fixed target block (50 normal + 25 anomaly,
position-invariant, identical across conditions) preceded by a normal-only prefix of
length 50; three conditions baseline(no prefix) / same-cat / cross-cat (prefix = the two
OTHER categories, mixed). The ONLY variable between same-cat and cross-cat is the prefix's
category identity (length 50 and normal-only composition matched and asserted in stream
validation). 3 cats × seeds 0–4 × 3 conditions = 45 cells; VisA checkpoint; per-position
within-block AUROC with 25-anomaly bootstrap CIs, per-cell and 15-cell aggregate.

Pre-registered decision (locked):
- **cross-cat fill drops below baseline AND same-cat fill stays flat vs baseline** →
  the collapse is caused by cross-category coreset contamination (not position/saturation);
  the §5.2 causal claim STANDS.
- **same-cat fill ALSO drops** → it is a position/saturation effect → RETRACT the
  cross-contamination causal claim and reframe §5.2 accordingly.
No outcome-dependent §5.2 rewrite until the Part-B numbers are in and reviewed.
