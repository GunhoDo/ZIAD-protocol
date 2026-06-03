#!/usr/bin/env python3
"""Summarize the OnlinePatchCoreLite FIFO-K reviewer diagnostic sweep."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow direct script execution.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.summarize_online_memory_diagnostic import (  # noqa: E402
    _escape_latex,
    _format_ci,
    summarize,
)

DEFAULT_ROOT = Path("results/latest/paper_candidate/diagnostic_online_patchcore_lite")
DEFAULT_OUTPUT_CSV = DEFAULT_ROOT / "online_patchcore_lite_k_sweep_summary.csv"
DEFAULT_OUTPUT_JSON = DEFAULT_ROOT / "online_patchcore_lite_k_sweep_summary.json"
DEFAULT_OUTPUT_TEX = Path("results/latest/tables/online_patchcore_lite_k_sweep.tex")
DEFAULT_COMPARISON_CSV = DEFAULT_ROOT / "online_memory_detector_comparison.csv"
DEFAULT_COMPARISON_JSON = DEFAULT_ROOT / "online_memory_detector_comparison.json"
DEFAULT_COMPARISON_TEX = Path("results/latest/tables/online_memory_detector_comparison.tex")
DEFAULT_REPORT = Path("docs/online_patchcore_lite_reviewer_report.md")
PILOT_CATEGORIES = ["bottle", "cable", "capsule"]
K_VALUES = [8, 16, 32, 64]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _summary_row(summary: dict[str, Any], *, detector: str) -> dict[str, Any]:
    ci_width = float(summary["delta_b_i_ci_high"]) - float(summary["delta_b_i_ci_low"])
    stream_lengths = summary.get("stream_lengths") or []
    return {
        "detector": detector,
        "dataset": summary["dataset"],
        "memory_policy": summary["memory_policy"],
        "categories": "|".join(summary["categories"]),
        "stream_length": int(stream_lengths[0]) if stream_lengths else "",
        "rows": summary["row_count"],
        "strata": summary["strata_count"],
        "delta_b_i": summary["delta_b_i_mean"],
        "ci_low": summary["delta_b_i_ci_low"],
        "ci_high": summary["delta_b_i_ci_high"],
        "ci_width": ci_width,
        "ci_excludes_zero": summary["delta_b_i_ci_excludes_zero"],
        "standard_error": summary["delta_b_i_standard_error"],
        "minimum_detectable_effect_95": summary["minimum_detectable_effect_95"],
        "mean_image_auroc": summary["mean_image_auroc"],
        "mean_latency_ms": summary["mean_latency_ms"],
        "paper_allowed": summary["paper_allowed"],
        "claim_allowed": summary["claim_allowed"],
        "review_status": summary["review_status"],
    }


def build_k_summaries(root: Path, k_values: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for k_value in k_values:
        k_root = root / f"k{k_value}"
        summary = summarize(
            k_root,
            categories=PILOT_CATEGORIES,
            dataset="MVTec AD",
            baseline="OnlinePatchCoreLite",
            memory_policy="FIFO",
            calibration="none",
        )
        summary["memory_size"] = k_value
        row = _summary_row(summary, detector=f"OnlinePatchCoreLite K={k_value}")
        row["memory_size"] = k_value
        rows.append(row)
    return rows


def _best_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    significant = [row for row in rows if row["ci_excludes_zero"]]
    candidates = significant or rows
    return max(candidates, key=lambda row: (abs(float(row["delta_b_i"])), -float(row["ci_width"])))


def _narrowest_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return min(rows, key=lambda row: float(row["ci_width"]))


def write_k_outputs(
    rows: list[dict[str, Any]],
    *,
    csv_path: Path,
    json_path: Path,
    tex_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "memory_size",
        "detector",
        "dataset",
        "rows",
        "strata",
        "delta_b_i",
        "ci_low",
        "ci_high",
        "ci_width",
        "ci_excludes_zero",
        "standard_error",
        "minimum_detectable_effect_95",
        "mean_image_auroc",
        "mean_latency_ms",
        "paper_allowed",
        "claim_allowed",
        "review_status",
    ]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in columns})

    best = _best_row(rows)
    narrowest = _narrowest_row(rows)
    json_path.write_text(
        json.dumps(
            {
                "status": "online_patchcore_lite_sweep_complete",
                "rows": rows,
                "strongest_effect": best,
                "narrowest_ci": narrowest,
                "best_reviewer_facing": best,
                "paper_allowed": False,
                "claim_allowed": False,
                "review_status": "review_pending",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    lines = [
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"K & Rows & Strata & $\Delta$B-I [95\% CI] & SE & MDE$_{95}$ & Lat. (ms) \\",
        r"\midrule",
    ]
    for row in rows:
        delta = _format_ci(row["delta_b_i"], row["ci_low"], row["ci_high"])
        if row["ci_excludes_zero"]:
            delta = r"\textbf{" + delta + "}"
        lines.append(
            f"{row['memory_size']} & {row['rows']} & {row['strata']} & {delta} & "
            f"{row['standard_error']:.3f} & {row['minimum_detectable_effect_95']:.3f} & "
            f"{row['mean_latency_ms']:.2f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    tex_path.write_text("\n".join(lines))


def build_comparison_rows(best_patchcore: dict[str, Any]) -> list[dict[str, Any]]:
    prototype = _read_json(
        Path("results/latest/paper_candidate/diagnostic_online_prototype_ema/"
             "online_memory_delta_bi_summary.json")
    )
    window = _read_json(
        Path("results/latest/paper_candidate/diagnostic_online_window_knn/"
             "online_memory_delta_bi_summary.json")
    )
    window_sl64 = _read_json(
        Path("results/latest/paper_candidate/diagnostic_online_window_knn_sl64/"
             "online_memory_delta_bi_summary.json")
    )
    patchcore_sl64 = _read_json(
        Path("results/latest/paper_candidate/diagnostic_online_patchcore_lite_sl64/k8/"
             "online_memory_delta_bi_summary.json")
    )
    rows: list[dict[str, Any]] = []
    if prototype:
        rows.append(_summary_row(prototype, detector="OnlinePrototypeEMA"))
    if window:
        rows.append(_summary_row(window, detector="OnlineWindowKNN"))
    if window_sl64:
        rows.append(_summary_row(window_sl64, detector="OnlineWindowKNN"))
    rows.append(
        {
            **best_patchcore,
            "detector": f"OnlinePatchCoreLite K={best_patchcore['memory_size']}",
            "stream_length": int(best_patchcore.get("stream_length") or 256),
        }
    )
    if patchcore_sl64:
        rows.append(_summary_row(patchcore_sl64, detector="OnlinePatchCoreLite K=8"))
    return rows


def _comparison_detector_tex(detector: str) -> str:
    if detector.startswith("OnlinePatchCoreLite K="):
        k_value = detector.split("K=", 1)[1]
        return f"OnlinePatchCoreLite $K{{=}}{_escape_latex(k_value)}$"
    return _escape_latex(detector)


def _comparison_mean_tex(row: dict[str, Any]) -> str:
    value = f"{float(row['delta_b_i']):+.3f}"
    if row["ci_excludes_zero"]:
        return r"\textbf{" + value + "}"
    return value


def _comparison_ci_tex(row: dict[str, Any]) -> str:
    value = f"[{float(row['ci_low']):+.3f}, {float(row['ci_high']):+.3f}]"
    if row["ci_excludes_zero"]:
        return r"\textbf{" + value + "}"
    return "$" + value + "$"


def write_comparison_outputs(
    rows: list[dict[str, Any]],
    *,
    csv_path: Path,
    json_path: Path,
    tex_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "detector",
        "dataset",
        "stream_length",
        "rows",
        "strata",
        "delta_b_i",
        "ci_low",
        "ci_high",
        "ci_excludes_zero",
        "standard_error",
        "mean_latency_ms",
    ]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in columns})
    json_path.write_text(
        json.dumps(
            {
                "status": "online_memory_detector_comparison_complete",
                "rows": rows,
                "paper_allowed": False,
                "claim_allowed": False,
                "review_status": "review_pending",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    lines = [
        r"\begin{tabular}{lccccccr}",
        r"\toprule",
        r"Detector & Len & Rows & Strata & \multicolumn{2}{c}{$\Delta$B-I} & Sig. & Lat. (ms) \\",
        r"\cmidrule(lr){5-6}",
        r"& & & & Mean & 95\% CI & & \\",
        r"\midrule",
    ]
    previous_family = ""
    for index, row in enumerate(rows):
        family = str(row["detector"]).split()[0]
        if index > 0 and family != previous_family:
            lines.append(r"\midrule")
        lines.append(
            f"{_comparison_detector_tex(row['detector'])} & {row['stream_length']} & "
            f"{row['rows']} & {row['strata']} & {_comparison_mean_tex(row)} & "
            f"{_comparison_ci_tex(row)} & {'yes' if row['ci_excludes_zero'] else 'no'} & "
            f"{row['mean_latency_ms']:.2f} \\\\"
        )
        previous_family = family
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    tex_path.write_text("\n".join(lines))


def write_report(path: Path, *, k_rows: list[dict[str, Any]], comparison_rows: list[dict[str, Any]]) -> None:
    best = _best_row(k_rows)
    significant = [row for row in k_rows if row["ci_excludes_zero"]]
    lines = [
        "# OnlinePatchCoreLite Reviewer Diagnostic",
        "",
        "This report summarizes a lightweight true-online PatchCore-style FIFO memory-bank detector.",
        "The detector scores each descriptor against the current memory bank before inserting it, so future scores depend on the previous stream prefix.",
        "",
        "## Per-K Results",
        "",
        "| K | Delta B-I | 95% CI | CI excludes zero | SE | MDE95 | Rows | Strata | Latency ms |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in k_rows:
        lines.append(
            f"| {row['memory_size']} | {row['delta_b_i']:+.6f} | "
            f"[{row['ci_low']:+.6f}, {row['ci_high']:+.6f}] | "
            f"{row['ci_excludes_zero']} | {row['standard_error']:.6f} | "
            f"{row['minimum_detectable_effect_95']:.6f} | {row['rows']} | "
            f"{row['strata']} | {row['mean_latency_ms']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Best Reviewer-Facing Result",
            "",
            (
                f"Best K: `{best['memory_size']}` with Delta B-I `{best['delta_b_i']:+.6f}` "
                f"and 95% CI `[{best['ci_low']:+.6f}, {best['ci_high']:+.6f}]`."
            ),
            f"CI excludes zero: `{best['ci_excludes_zero']}`.",
            "",
            "## Detector Comparison",
            "",
            "| Detector | Delta B-I | 95% CI | CI excludes zero | Rows | Strata | Latency ms |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| {row['detector']} | {row['delta_b_i']:+.6f} | "
            f"[{row['ci_low']:+.6f}, {row['ci_high']:+.6f}] | "
            f"{row['ci_excludes_zero']} | {row['rows']} | {row['strata']} | "
            f"{row['mean_latency_ms']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Reviewer-Facing Conclusion",
            "",
            (
                "Success: at least one OnlinePatchCoreLite configuration has a bootstrap "
                "95% CI excluding zero."
                if significant
                else "Not successful: no OnlinePatchCoreLite configuration has a bootstrap 95% CI excluding zero."
            ),
            "All outputs remain paper_allowed=false and claim_allowed=false.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    parser.add_argument("--comparison-csv", type=Path, default=DEFAULT_COMPARISON_CSV)
    parser.add_argument("--comparison-json", type=Path, default=DEFAULT_COMPARISON_JSON)
    parser.add_argument("--comparison-tex", type=Path, default=DEFAULT_COMPARISON_TEX)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--k-values", nargs="*", type=int, default=K_VALUES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    k_rows = build_k_summaries(args.root, args.k_values)
    write_k_outputs(k_rows, csv_path=args.output_csv, json_path=args.output_json, tex_path=args.output_tex)
    best = _best_row(k_rows)
    comparison_rows = build_comparison_rows(best)
    write_comparison_outputs(
        comparison_rows,
        csv_path=args.comparison_csv,
        json_path=args.comparison_json,
        tex_path=args.comparison_tex,
    )
    write_report(args.report, k_rows=k_rows, comparison_rows=comparison_rows)
    print(args.output_csv)
    print(args.output_json)
    print(args.output_tex)
    print(args.comparison_csv)
    print(args.comparison_json)
    print(args.comparison_tex)
    print(args.report)
    print(
        "status=online_patchcore_lite_sweep_complete "
        f"configs={len(k_rows)} best_k={best['memory_size']} "
        f"delta_b_i={best['delta_b_i']:+.6f} "
        f"ci=[{best['ci_low']:+.6f},{best['ci_high']:+.6f}] "
        f"excludes_zero={best['ci_excludes_zero']} paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
