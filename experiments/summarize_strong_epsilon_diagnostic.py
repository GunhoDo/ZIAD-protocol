#!/usr/bin/env python3
"""Summarize completed strong-epsilon diagnostic shards without inference."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_INPUT_ROOT = Path("results/latest/paper_candidate/diagnostic_strong_epsilon")
DEFAULT_OUTPUT_CSV = DEFAULT_INPUT_ROOT / "strong_epsilon_completed_summary.csv"
DEFAULT_OUTPUT_JSON = DEFAULT_INPUT_ROOT / "strong_epsilon_completed_summary.json"
DEFAULT_OUTPUT_TEX = Path("results/latest/tables/strong_epsilon_completed_summary.tex")

METRICS = ["image_auroc", "aupr", "ece", "latency_ms", "crd_lite"]
REQUIRED_COLUMNS = {
    "dataset",
    "stream_type",
    "contamination_epsilon",
    "baseline",
    "memory_policy",
    "calibration",
    "category",
    "status",
    *METRICS,
}


class StrongEpsilonSummaryError(ValueError):
    """Raised when strong-epsilon diagnostic inputs are invalid."""


def _parse_float(value: Any, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise StrongEpsilonSummaryError(f"Invalid numeric value for {field}: {value!r}") from exc
    if not math.isfinite(parsed):
        raise StrongEpsilonSummaryError(f"Non-finite numeric value for {field}: {value!r}")
    return parsed


def _mean(values: list[float]) -> float:
    if not values:
        raise StrongEpsilonSummaryError("Cannot average an empty value list")
    return sum(values) / len(values)


def _metrics_paths(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.glob("*/*/*/none/*/metrics.csv")
        if "/production_runs/" not in path.as_posix()
    )


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))
        if missing:
            raise StrongEpsilonSummaryError(f"Missing columns in {path}: {missing}")
        rows = list(reader)
    if not rows:
        raise StrongEpsilonSummaryError(f"Metrics file has no rows: {path}")
    for row in rows:
        if row.get("status") != "measured_paper_candidate":
            raise StrongEpsilonSummaryError(f"Unexpected row status in {path}: {row.get('status')}")
        for metric in METRICS:
            _parse_float(row.get(metric), field=metric)
    return rows


def _read_crd_rows(metrics_path: Path) -> list[dict[str, str]]:
    crd_path = metrics_path.parent / "crd_lite.csv"
    if not crd_path.exists():
        raise StrongEpsilonSummaryError(f"Missing CRD-lite CSV: {crd_path}")
    with crd_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted({"run_dir", "image_auroc_drop", "aupr_drop", "crd_lite"} - set(reader.fieldnames or []))
        if missing:
            raise StrongEpsilonSummaryError(f"Missing CRD-lite columns in {crd_path}: {missing}")
        rows = list(reader)
    if not rows:
        raise StrongEpsilonSummaryError(f"CRD-lite CSV has no rows: {crd_path}")
    for row in rows:
        for field in ["image_auroc_drop", "aupr_drop", "crd_lite"]:
            _parse_float(row.get(field), field=field)
    return rows


def summarize(input_root: Path = DEFAULT_INPUT_ROOT) -> dict[str, Any]:
    metric_paths = _metrics_paths(input_root)
    if not metric_paths:
        raise StrongEpsilonSummaryError(f"No completed aggregate metrics found under {input_root}")

    all_rows: list[dict[str, str]] = []
    all_crd_rows: list[dict[str, str]] = []
    for path in metric_paths:
        all_rows.extend(_read_rows(path))
        all_crd_rows.extend(_read_crd_rows(path))

    grouped: dict[tuple[str, str, str, str, str, float], list[dict[str, str]]] = defaultdict(list)
    for row in all_rows:
        grouped[
            (
                row["dataset"],
                row["baseline"],
                row["memory_policy"],
                row["calibration"],
                row["category"],
                _parse_float(row["contamination_epsilon"], field="contamination_epsilon"),
            )
        ].append(row)

    crd_grouped: dict[tuple[str, str, str, str, str, float], list[dict[str, str]]] = defaultdict(list)
    for row in all_crd_rows:
        crd_grouped[
            (
                row["dataset"],
                row["baseline"],
                row["memory_policy"],
                row["calibration"],
                row["category"],
                _parse_float(row["contamination_epsilon"], field="contamination_epsilon"),
            )
        ].append(row)

    output_rows: list[dict[str, Any]] = []
    for (dataset, baseline, memory_policy, calibration, category, epsilon), rows in sorted(
        grouped.items()
    ):
        streams = sorted({row["stream_type"] for row in rows})
        crd_rows = crd_grouped.get(
            (dataset, baseline, memory_policy, calibration, category, epsilon), []
        )
        if not crd_rows:
            raise StrongEpsilonSummaryError(
                f"Missing CRD-lite rows for {dataset}|{baseline}|{category}|{epsilon}"
            )
        output_rows.append(
            {
                "dataset": dataset,
                "baseline": baseline,
                "memory_policy": memory_policy,
                "calibration": calibration,
                "category": category,
                "epsilon": epsilon,
                "stream_types": "|".join(streams),
                "row_count": len(rows),
                **{
                    f"mean_{metric}": _mean(
                        [_parse_float(row[metric], field=metric) for row in rows]
                    )
                    for metric in METRICS
                },
                "mean_image_auroc_drop": _mean(
                    [_parse_float(row["image_auroc_drop"], field="image_auroc_drop") for row in crd_rows]
                ),
                "mean_aupr_drop": _mean(
                    [_parse_float(row["aupr_drop"], field="aupr_drop") for row in crd_rows]
                ),
            }
        )

    return {
        "status": "strong_epsilon_completed_summary",
        "run_tier": "paper_candidate",
        "candidate_scope": "diagnostic_completed_categories",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "input_root": str(input_root),
        "completed_category_count": len({row["category"] for row in all_rows}),
        "row_count": len(all_rows),
        "summary_row_count": len(output_rows),
        "rows": output_rows,
        "notes": (
            "Diagnostic summary over completed strong-epsilon category shards only. "
            "It does not imply full VisA coverage and does not promote paper or claim gates."
        ),
    }


def write_outputs(summary: dict[str, Any], csv_path: Path, json_path: Path, tex_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    fieldnames = [
        "dataset",
        "baseline",
        "category",
        "epsilon",
        "row_count",
        "mean_image_auroc",
        "mean_aupr",
        "mean_image_auroc_drop",
        "mean_aupr_drop",
        "mean_ece",
        "mean_latency_ms",
        "mean_crd_lite",
    ]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in summary["rows"]:
            writer.writerow({field: row[field] for field in fieldnames})

    lines = [
        "\\begin{tabular}{@{}lllrrrrrr@{}}",
        "\\toprule",
        "Dataset & Baseline & Category & $\\epsilon$ & Rows & AUROC & AUROC term & AUPR term & CRD-lite \\\\",
        "\\midrule",
    ]
    for row in summary["rows"]:
        lines.append(
            f"{row['dataset']} & {row['baseline']} & {row['category']} & "
            f"{row['epsilon']:.2f} & {row['row_count']} & "
            f"{row['mean_image_auroc']:.3f} & {row['mean_image_auroc_drop']:+.3f} & "
            f"{row['mean_aupr_drop']:+.3f} & {row['mean_crd_lite']:+.3f} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    tex_path.write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize(args.input_root)
    write_outputs(summary, args.output_csv, args.output_json, args.output_tex)
    print(args.output_csv)
    print(args.output_json)
    print(args.output_tex)
    print(
        "status=strong_epsilon_completed_summary "
        f"categories={summary['completed_category_count']} rows={summary['row_count']} "
        "paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
