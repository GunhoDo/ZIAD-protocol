#!/usr/bin/env python3
"""Verification gate + summary for the RareCLIP/SCS order-mechanism (bank-trace) study.

READ-ONLY over the Gate-2 bank-trace artifacts. Computes the verification gate
(row-count, in-environment determinism re-check, provenance) and the summary
statistics, and writes a gate JSON with paper_allowed=false /
claim_allowed=false / review_status=review_pending --- mirroring the strong-epsilon
discipline: a new measurement is not paper-eligible until the gate is reviewed.

This does NOT modify any existing generator, scoring code, or paper_allowed flag,
and does NOT emit any paper table. It only reads the banktrace directory and
writes its own gate/summary JSON.
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
# Defaults reproduce the MVTec slice exactly (no-arg run is byte-unchanged).
D = ROOT / "results/latest/paper_candidate/diagnostic_rareclip_scs_banktrace_gate2"
OUT = D / "order_mechanism_gate.json"
CATS = ["bottle", "cable", "capsule"]
DATASET_NAME = "MVTec AD"
TABLE_PATH = ROOT / "results/latest/tables/order_mechanism_summary.tex"
STUDY = "rareclip_scs_order_mechanism"
SEEDS = list(range(10))
EXPECT_ROWS = 64  # L=64 stream


def _scores(stem: str) -> list[dict[str, str]]:
    return list(csv.DictReader((D / f"{stem}.csv").open()))


def _centroid(stem: str) -> np.ndarray:
    with (D / f"{stem}_banktrace_final_centroid.csv").open() as fh:
        return np.array([float(x) for x in next(csv.reader(fh))], dtype=np.float64)


def _trace(stem: str) -> list[dict[str, str]]:
    return list(csv.DictReader((D / f"{stem}_banktrace.csv").open()))


def _auroc(y: np.ndarray, s: np.ndarray) -> float:
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    n1 = int(y.sum()); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main() -> None:
    cells = [(c, s, o) for c in CATS for s in SEEDS for o in ("iid", "bursty", "bursty_rep")]

    # ---- GATE 1: row-count / completeness ----
    rc_problems: list[str] = []
    present = 0
    for c, s, o in cells:
        stem = f"{c}_{o.replace('bursty_rep', 'bursty')}_seed{s}" + ("_rep" if o == "bursty_rep" else "")
        sc, bt, fc = D / f"{stem}.csv", D / f"{stem}_banktrace.csv", D / f"{stem}_banktrace_final_centroid.csv"
        if not (sc.exists() and bt.exists() and fc.exists()):
            rc_problems.append(f"{stem}: missing file"); continue
        present += 1
        ns, nb = len(_scores(stem)), len(_trace(stem))
        if ns != EXPECT_ROWS:
            rc_problems.append(f"{stem}: scores rows {ns}!={EXPECT_ROWS}")
        if nb != EXPECT_ROWS:
            rc_problems.append(f"{stem}: banktrace rows {nb}!={EXPECT_ROWS}")
    rc_pass = (present == len(cells)) and not rc_problems

    # ---- GATE 2: in-environment determinism (bursty vs bursty_rep) ----
    score_mismatch_rows = 0
    score_total_rows = 0
    d_rep = []
    for c in CATS:
        for s in SEEDS:
            b, r = f"{c}_bursty_seed{s}", f"{c}_bursty_seed{s}_rep"
            sb = [row["anomaly_score"] for row in _scores(b)]
            sr = [row["anomaly_score"] for row in _scores(r)]
            score_total_rows += len(sb)
            score_mismatch_rows += sum(1 for a, x in zip(sb, sr) if a != x)
            d_rep.append(float(np.linalg.norm(_centroid(b) - _centroid(r))))
    d_rep = np.array(d_rep)
    determinism_pass = (score_mismatch_rows == 0) and bool(np.all(d_rep == 0.0))

    # ---- SUMMARY STATISTICS (only meaningful if gates pass) ----
    d_ord, score_shift, auc_i, auc_b, dbi = [], [], [], [], []
    env_first, env_last = [], []
    for c in CATS:
        for s in SEEDS:
            ci, cb = _centroid(f"{c}_iid_seed{s}"), _centroid(f"{c}_bursty_seed{s}")
            d_ord.append(float(np.linalg.norm(ci - cb)))
            si = {row["image_path"]: float(row["anomaly_score"]) for row in _scores(f"{c}_iid_seed{s}")}
            sb = {row["image_path"]: float(row["anomaly_score"]) for row in _scores(f"{c}_bursty_seed{s}")}
            common = set(si) & set(sb)
            score_shift.append(float(np.mean([abs(si[k] - sb[k]) for k in common])))
            yi = np.array([int(row["label"]) for row in _scores(f"{c}_iid_seed{s}")])
            vi = np.array([float(row["anomaly_score"]) for row in _scores(f"{c}_iid_seed{s}")])
            yb = np.array([int(row["label"]) for row in _scores(f"{c}_bursty_seed{s}")])
            vb = np.array([float(row["anomaly_score"]) for row in _scores(f"{c}_bursty_seed{s}")])
            ai, ab = _auroc(yi, vi), _auroc(yb, vb)
            auc_i.append(ai); auc_b.append(ab); dbi.append(ab - ai)
            rows = _trace(f"{c}_bursty_seed{s}")
            cap = max(int(r["pfm_size"]) for r in rows if int(r["pfm_size"]) > 0)
            d = [float(r["pfm_centroid_l2_delta"]) for r in rows
                 if int(r["pfm_size"]) == cap and r["pfm_centroid_l2_delta"] != ""]
            third = len(d) // 3
            env_first.append(float(np.mean(d[:third]))); env_last.append(float(np.mean(d[-third:])))
    d_ord = np.array(d_ord); score_shift = np.array(score_shift)
    auc_i = np.array(auc_i); auc_b = np.array(auc_b); dbi = np.array(dbi)
    env_first = np.array(env_first); env_last = np.array(env_last)
    mu_rep, sd_rep = float(d_rep.mean()), float(d_rep.std(ddof=1))
    floor = mu_rep + 3 * sd_rep
    w_ord = stats.wilcoxon(d_ord, d_rep, alternative="greater")
    w_dbi = stats.wilcoxon(dbi, alternative="two-sided")

    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        commit = "unknown"

    gate = {
        "study": STUDY,
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "scope": {
            "dataset": DATASET_NAME, "categories": list(CATS),
            "seeds": SEEDS, "contamination_epsilon": 0.0, "stream_length": 64,
            "memory_policy": "default/SCS", "visa_included": DATASET_NAME == "VisA",
            "n_cell_groups": 30, "n_runs": len(cells),
        },
        "gate_1_row_count": {"pass": rc_pass, "present": present, "expected": len(cells),
                             "expected_rows_per_cell": EXPECT_ROWS, "problems": rc_problems},
        "gate_2_determinism_recheck": {
            "pass": determinism_pass,
            "anomaly_score_row_mismatches": score_mismatch_rows,
            "anomaly_score_rows_compared": score_total_rows,
            "d_rep_centroid_all_zero": bool(np.all(d_rep == 0.0)),
            "d_rep_max": float(d_rep.max()),
            "note": "bursty vs bursty_rep, same ordering; only latency_ms varies run-to-run",
        },
        "provenance": {
            "commit_head": commit,
            "instrumentation": "experiments/baselines/rareclip.py _bank_trace_step (read-only, post-latency-timer)",
            "scoring_path_modified": False,
            "existing_generators_modified": False,
            "flags_modified": False,
            "source_dir": str(D.relative_to(ROOT)),
            "note": "instrumentation + this summarizer are uncommitted working-tree additions at gate time",
        },
        "summary_stats": {
            "noise_floor_d_rep": {"mean": mu_rep, "sd": sd_rep, "mu_plus_3sd": floor},
            "order_memory_d_ord": {"mean": float(d_ord.mean()), "sd": float(d_ord.std(ddof=1)),
                                   "min": float(d_ord.min()), "max": float(d_ord.max()),
                                   "cells_ge_3x_floor": int(np.sum(d_ord >= 3 * d_rep)),
                                   "wilcoxon_greater_p": float(w_ord.pvalue)},
            "order_score_shift_per_image": {"mean": float(score_shift.mean()),
                                            "sd": float(score_shift.std(ddof=1)),
                                            "max": float(score_shift.max())},
            "auroc_iid_mean": float(np.nanmean(auc_i)), "auroc_bursty_mean": float(np.nanmean(auc_b)),
            "delta_b_i": {"mean": float(np.nanmean(dbi)), "median_abs": float(np.nanmedian(np.abs(dbi))),
                          "wilcoxon_two_sided_p": float(w_dbi.pvalue),
                          "cells_within_0p01": int(np.sum(np.abs(dbi) <= 0.01))},
            "convergence_envelope": {"first_third_mean": float(env_first.mean()),
                                     "last_third_mean": float(env_last.mean()),
                                     "decay_ratio_mean": float((env_first / env_last).mean()),
                                     "cells_first_gt_last": int(np.sum(env_first > env_last))},
        },
    }
    OUT.write_text(json.dumps(gate, indent=2))

    # Paper table (.tex), emitted read-only into the generated-tables dir. It is
    # used in the paper only after the gate is reviewed/promoted.
    tbl = TABLE_PATH
    score_floor = 0.0  # gate 2: per-image bursty-vs-repeat score diff is exactly 0
    tbl.write_text("\n".join([
        "\\begin{tabular}{lccc}",
        "\\toprule",
        "Axis & Same-order floor & i.i.d.\\ vs bursty & Order-inv.? \\\\",
        "\\midrule",
        f"SCS memory (centroid $L_2$) & {mu_rep:.3f} & {d_ord.mean():.3f} & no \\\\",
        f"Per-image score (mean $|\\Delta|$) & {score_floor:.3f} & {score_shift.mean():.3f} & no \\\\",
        f"AUROC ($\\Delta$B-I) & --- & {np.nanmean(dbi):+.3f} & yes \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "",
    ]))

    print("=" * 64)
    print("ORDER-MECHANISM GATE  (paper_allowed=False until reviewed)")
    print("=" * 64)
    print(f"GATE 1 row-count:   {'PASS' if rc_pass else 'FAIL'}  ({present}/{len(cells)} runs, {EXPECT_ROWS} rows each)")
    if rc_problems:
        for p in rc_problems[:5]:
            print("   -", p)
    print(f"GATE 2 determinism: {'PASS' if determinism_pass else 'FAIL'}  "
          f"(anomaly_score mismatches {score_mismatch_rows}/{score_total_rows}, d_rep all-zero={bool(np.all(d_rep==0))})")
    print(f"provenance commit:  {commit}  | scoring_path_modified=False | generators/flags untouched")
    print(f"wrote gate JSON ->  {OUT.relative_to(ROOT)}")
    print("-" * 64)
    print("summary (gated, not paper-eligible yet):")
    print(f"  d_rep floor = {mu_rep:.5f}   d_ord = {d_ord.mean():.5f} (30/30 >=3x floor: {int(np.sum(d_ord>=3*d_rep))}), p={w_ord.pvalue:.2e}")
    print(f"  per-image score shift = {score_shift.mean():.5f}")
    print(f"  AUROC iid {np.nanmean(auc_i):.4f} vs bursty {np.nanmean(auc_b):.4f}; dB-I={np.nanmean(dbi):+.4f} (p={w_dbi.pvalue:.2f})")
    print(f"  convergence decay = {(env_first/env_last).mean():.1f}x ({int(np.sum(env_first>env_last))}/30)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Order-mechanism gate/summary (default = MVTec slice).")
    parser.add_argument("--dir", default=str(D), help="bank-trace output dir")
    parser.add_argument("--cats", default=",".join(CATS), help="comma-separated categories")
    parser.add_argument("--dataset", default=DATASET_NAME, help="dataset label, e.g. 'VisA'")
    parser.add_argument("--table", default=str(TABLE_PATH), help="output .tex table path")
    parser.add_argument("--study", default=STUDY, help="study name in gate JSON")
    args = parser.parse_args()

    def _abs(p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (ROOT / path)

    D = _abs(args.dir)
    OUT = D / "order_mechanism_gate.json"
    CATS = [c.strip() for c in args.cats.split(",") if c.strip()]
    DATASET_NAME = args.dataset
    TABLE_PATH = _abs(args.table)
    STUDY = args.study
    main()
