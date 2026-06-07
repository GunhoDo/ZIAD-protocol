#!/usr/bin/env python3
"""Concat (multi-category distribution-shift) gate + Rule-7 verdict. READ-ONLY over the
concat bank-trace artifacts. Emits a gate JSON (paper_allowed=false) in the summarize
pattern. Verdict = within-category AUROC position-invariance (effect size first), with the
boundary drift spike reported as the A/B-common memory signal. No paper edits, no flags flipped.
"""
from __future__ import annotations

import csv, json, subprocess
from pathlib import Path
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "results/latest/paper_candidate/diagnostic_rareclip_scs_concat_visa_gate2"
OUT = D / "concat_order_mechanism_gate.json"
PERMS, SEEDS = range(3), range(5)
EXPECT_ROWS = 315
FLOOR = 0.01093            # VisA single-category within-category median |dB-I|
THRESH = 3 * FLOOR         # ~0.0328
# cyclic permutations -> category at each position
SEQS = {0: ["candle", "macaroni1", "macaroni2"],
        1: ["macaroni1", "macaroni2", "candle"],
        2: ["macaroni2", "candle", "macaroni1"]}


def rows(stem):
    return list(csv.DictReader((D / f"{stem}.csv").open()))


def centroid(stem):
    with (D / f"{stem}_banktrace_final_centroid.csv").open() as fh:
        return np.array([float(x) for x in next(csv.reader(fh))])


def auroc(y, s):
    o = np.argsort(s, kind="mergesort"); r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    n1 = int(y.sum()); n0 = len(y) - n1
    return float("nan") if n1 == 0 or n0 == 0 else float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def within_block_auroc(stem, category):
    # Each block is one category; scores.csv carries per-row category, so filter by it.
    rs = [r for r in rows(stem) if r["category"] == category]
    y = np.array([int(r["label"]) for r in rs]); s = np.array([float(r["anomaly_score"]) for r in rs])
    return auroc(y, s)


# ---- GATE 1: row-count ----
rc_problems, present = [], 0
for p in PERMS:
    for s in SEEDS:
        for rep in ("", "_rep"):
            stem = f"perm{p}_seed{s}{rep}"
            if not (D / f"{stem}_banktrace_final_centroid.csv").exists():
                rc_problems.append(f"{stem}: missing"); continue
            present += 1
            n = len(rows(stem))
            if n != EXPECT_ROWS:
                rc_problems.append(f"{stem}: {n} rows")
rc_pass = present == 30 and not rc_problems

# ---- GATE 2: determinism (base vs repeat) ----
mismatch = total = 0
d_rep = []
for p in PERMS:
    for s in SEEDS:
        b, r = f"perm{p}_seed{s}", f"perm{p}_seed{s}_rep"
        sb = [x["anomaly_score"] for x in rows(b)]; sr = [x["anomaly_score"] for x in rows(r)]
        total += len(sb); mismatch += sum(1 for a, c in zip(sb, sr) if a != c)
        d_rep.append(float(np.linalg.norm(centroid(b) - centroid(r))))
d_rep = np.array(d_rep)
det_pass = mismatch == 0 and bool(np.all(d_rep == 0.0))

# ---- PRIMARY: within-category AUROC position-Delta (base runs) ----
# within_auroc[cat][seed][position]
within = {c: {s: {} for s in SEEDS} for c in ["candle", "macaroni1", "macaroni2"]}
for p in PERMS:
    for s in SEEDS:
        for pos, cat in enumerate(SEQS[p]):
            within[cat][s][pos] = within_block_auroc(f"perm{p}_seed{s}", cat)
pos_deltas = []      # AUROC(pos_k) - AUROC(pos0), k=1,2
per_cat = {}
for cat in within:
    cds = []
    for s in SEEDS:
        a0 = within[cat][s][0]
        for k in (1, 2):
            cds.append(within[cat][s][k] - a0)
    per_cat[cat] = {"mean_abs": float(np.mean(np.abs(cds))), "mean_signed": float(np.mean(cds)),
                    "auroc_pos0_mean": float(np.mean([within[cat][s][0] for s in SEEDS])),
                    "auroc_pos1_mean": float(np.mean([within[cat][s][1] for s in SEEDS])),
                    "auroc_pos2_mean": float(np.mean([within[cat][s][2] for s in SEEDS]))}
    pos_deltas += cds
pos_deltas = np.array(pos_deltas)
mean_abs_delta = float(np.mean(np.abs(pos_deltas)))
# secondary: is |position-Delta| materially larger than the within-category baseline floor?
w = stats.wilcoxon(np.abs(pos_deltas) - FLOOR, alternative="greater")

if mean_abs_delta <= THRESH * 0.8:
    verdict = "A_rank_preservation_robust"
elif mean_abs_delta >= THRESH * 1.2:
    verdict = "B_stationarity_conditional"
else:
    verdict = "AMBIGUOUS_use_secondary_then_more_seeds"

# ---- boundary drift spike (A/B-common memory signal) ----
boundary_ratios = {105: [], 210: []}
interior_medians = []
for p in PERMS:
    for s in SEEDS:
        bt = list(csv.DictReader((D / f"perm{p}_seed{s}_banktrace.csv").open()))
        cap = max(int(r["pfm_size"]) for r in bt if int(r["pfm_size"]) > 0)
        dmap = {int(r["stream_index"]): (float(r["pfm_centroid_l2_delta"]) if r["pfm_centroid_l2_delta"] != "" else None) for r in bt}
        interior = [v for i, v in dmap.items() if v is not None and int(bt[i]["pfm_size"]) == cap and i not in (104,105,106,209,210,211)]
        med = float(np.median(interior)); interior_medians.append(med)
        for b in (105, 210):
            win = [dmap[i] for i in range(b, b + 3) if dmap.get(i) is not None]
            boundary_ratios[b].append(max(win) / med if med > 0 else float("nan"))

# ---- whole-mixed AUROC (context only, confounded) ----
mixed = []
for p in PERMS:
    for s in SEEDS:
        rs = rows(f"perm{p}_seed{s}")
        mixed.append(auroc(np.array([int(r["label"]) for r in rs]), np.array([float(r["anomaly_score"]) for r in rs])))

try:
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"]).decode().strip()
except Exception:
    commit = "unknown"

gate = {
    "study": "rareclip_scs_concat_order_mechanism",
    "paper_allowed": False, "claim_allowed": False, "review_status": "review_pending",
    "scope": {"dataset": "VisA", "categories": ["candle", "macaroni1", "macaroni2"],
              "design": "3 cyclic permutations x seeds 0-4, concatenated length ~315, prevalence 0.05, eps=0, iid within block, default SCS",
              "n_runs": 30},
    "gate_1_row_count": {"pass": rc_pass, "present": present, "expected": 30, "problems": rc_problems},
    "gate_2_determinism": {"pass": det_pass, "anomaly_score_mismatches": mismatch, "rows_compared": total,
                           "d_rep_all_zero": bool(np.all(d_rep == 0.0)), "d_rep_max": float(d_rep.max())},
    "provenance": {"commit_head": commit, "scoring_path_modified": False, "existing_generators_modified": False,
                   "flags_modified": False, "source_dir": str(D.relative_to(ROOT))},
    "rule7_verdict": {
        "floor": FLOOR, "threshold_3x": THRESH,
        "within_category_position_delta_mean_abs": mean_abs_delta,
        "position_delta_max_abs": float(np.max(np.abs(pos_deltas))),
        "per_category": per_cat,
        "secondary_wilcoxon_absdelta_gt_floor_p": float(w.pvalue),
        "verdict": verdict,
        "boundary_drift_spike_xinterior": {str(b): float(np.nanmean(v)) for b, v in boundary_ratios.items()},
        "whole_mixed_auroc_mean_CONTEXT_ONLY": float(np.nanmean(mixed)),
    },
}
OUT.write_text(json.dumps(gate, indent=2))

print("=" * 66)
print("CONCAT ORDER-MECHANISM GATE (Rule 7)   paper_allowed=False")
print("=" * 66)
print(f"GATE 1 row-count:   {'PASS' if rc_pass else 'FAIL'} ({present}/30, 315 rows)")
print(f"GATE 2 determinism: {'PASS' if det_pass else 'FAIL'} (score mismatch {mismatch}/{total}, d_rep all-zero={bool(np.all(d_rep==0))})")
print(f"provenance: {commit} | scoring/generators/flags untouched")
print("-" * 66)
print(f"FLOOR={FLOOR}  3x threshold={THRESH:.4f}")
print(f"within-category AUROC position-Delta: mean|Δ|={mean_abs_delta:.4f}  max|Δ|={np.max(np.abs(pos_deltas)):.4f}")
for c, v in per_cat.items():
    print(f"  {c:10s} pos0/1/2 AUROC = {v['auroc_pos0_mean']:.3f}/{v['auroc_pos1_mean']:.3f}/{v['auroc_pos2_mean']:.3f}  mean|Δ|={v['mean_abs']:.4f}")
print(f"secondary Wilcoxon(|Δ|>floor) p={w.pvalue:.3g}")
print(f">>> RULE 7 VERDICT: {verdict}")
print(f"boundary drift spike x interior (A/B-common): 105={np.nanmean(boundary_ratios[105]):.1f}x  210={np.nanmean(boundary_ratios[210]):.1f}x")
print(f"whole-mixed AUROC (context only, confounded): {np.nanmean(mixed):.3f}")
print(f"wrote {OUT.relative_to(ROOT)}")
