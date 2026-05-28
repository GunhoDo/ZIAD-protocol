#!/usr/bin/env python3
"""Summarize completed stream-length sensitivity shards without inference."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

DEFAULT_INPUT_ROOT = Path("results/latest/sensitivity/stream_length")
DEFAULT_CSV = DEFAULT_INPUT_ROOT / "summary.csv"
DEFAULT_JSON = DEFAULT_INPUT_ROOT / "summary.json"
DEFAULT_TEX = Path("results/latest/tables/stream_length_sensitivity_summary.tex")
METRIC_COLUMNS = ["image_auroc", "aupr", "ece", "latency_ms", "crd_lite"]
OUTPUT_COLUMNS = [
    "dataset",
    "baseline",
    "memory_policy",
    "calibration",
    "stream_length",
    "completed_categories",
    "categories",
    "total_rows",
    "mean_image_auroc",
    "mean_aupr",
    "mean_ece",
    "mean_latency_ms",
    "mean_crd_lite",
    "paper_allowed",
    "claim_allowed",
    "review_status",
]


def _float_or_none(value: str | None) -> float | None:
    if value in {None, "", "NA"}:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite metric value: {value}")
    return number


def _format(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.6f}"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return payload


def _completed_manifests(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.glob("**/manifest.json")
        if path.parent.name.startswith("len_")
    )


def summarize(input_root: Path = DEFAULT_INPUT_ROOT) -> dict[str, Any]:
    groups: dict[tuple[str, str, str, str, int], dict[str, Any]] = {}
    errors: list[str] = []
    for manifest_path in _completed_manifests(input_root):
        try:
            manifest = _load_json(manifest_path)
            if manifest.get("status") != "measured_stream_length_sensitivity_complete":
                continue
            if manifest.get("paper_allowed") is not False:
                errors.append(f"paper_allowed opened: {manifest_path}")
            if manifest.get("claim_allowed") is not False:
                errors.append(f"claim_allowed opened: {manifest_path}")
            if manifest.get("review_status") != "review_pending":
                errors.append(f"review_status mismatch: {manifest_path}")
            metrics_path = Path(str(manifest.get("aggregate_metrics", manifest_path.parent / "metrics.csv")))
            if not metrics_path.exists():
                errors.append(f"missing metrics: {metrics_path}")
                continue
            with metrics_path.open(newline="") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
            expected = int(manifest.get("expected_full_run_count") or manifest.get("run_count") or 0)
            if len(rows) != expected:
                errors.append(f"row count {len(rows)} != expected {expected}: {metrics_path}")
            statuses = {row.get("status") for row in rows}
            if statuses != {"measured_stream_length_sensitivity"}:
                errors.append(f"unexpected statuses {statuses}: {metrics_path}")
            key = (
                str(manifest.get("dataset", "")),
                str(manifest.get("baseline", "")),
                str(manifest.get("memory_policy", "")),
                str(manifest.get("calibration", "")),
                int(manifest.get("stream_length", 0)),
            )
            group = groups.setdefault(
                key,
                {
                    "categories": set(),
                    "rows": [],
                    "paper_allowed": False,
                    "claim_allowed": False,
                    "review_status": "review_pending",
                },
            )
            group["categories"].add(str(manifest.get("category", "")))
            group["rows"].extend(rows)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            errors.append(f"{manifest_path}: {error}")

    summary_rows: list[dict[str, Any]] = []
    for (dataset, baseline, memory_policy, calibration, stream_length), group in sorted(groups.items()):
        rows = group["rows"]
        metric_means: dict[str, float | None] = {}
        for metric in METRIC_COLUMNS:
            values = [_float_or_none(row.get(metric)) for row in rows]
            finite_values = [value for value in values if value is not None]
            metric_means[metric] = mean(finite_values) if finite_values else None
        categories = sorted(group["categories"])
        summary_rows.append(
            {
                "dataset": dataset,
                "baseline": baseline,
                "memory_policy": memory_policy,
                "calibration": calibration,
                "stream_length": stream_length,
                "completed_categories": len(categories),
                "categories": "|".join(categories),
                "total_rows": len(rows),
                "mean_image_auroc": metric_means["image_auroc"],
                "mean_aupr": metric_means["aupr"],
                "mean_ece": metric_means["ece"],
                "mean_latency_ms": metric_means["latency_ms"],
                "mean_crd_lite": metric_means["crd_lite"],
                "paper_allowed": False,
                "claim_allowed": False,
                "review_status": "review_pending",
            }
        )

    status = (
        "stream_length_sensitivity_summary_failed"
        if errors
        else "stream_length_sensitivity_summary_complete"
        if summary_rows
        else "stream_length_sensitivity_summary_empty"
    )
    return {
        "status": status,
        "input_root": str(input_root),
        "group_count": len(summary_rows),
        "error_count": len(errors),
        "errors": errors,
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "rows": summary_rows,
        "notes": (
            "Appendix stream-length sensitivity summary. Empty status is expected "
            "before sensitivity shards are executed."
        ),
    }


def write_outputs(
    summary: dict[str, Any],
    *,
    csv_path: Path = DEFAULT_CSV,
    json_path: Path = DEFAULT_JSON,
    tex_path: Path = DEFAULT_TEX,
) -> tuple[Path, Path, Path]:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in summary["rows"]:
            writer.writerow(
                {
                    **row,
                    "mean_image_auroc": _format(row["mean_image_auroc"]),
                    "mean_aupr": _format(row["mean_aupr"]),
                    "mean_ece": _format(row["mean_ece"]),
                    "mean_latency_ms": _format(row["mean_latency_ms"]),
                    "mean_crd_lite": _format(row["mean_crd_lite"]),
                }
            )
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    if summary["rows"]:
        lines = [
            "\\begin{tabular}{llrrrr}",
            "\\toprule",
            "Dataset & Baseline & Len. & Cats & Rows & AUROC \\\\",
            "\\midrule",
        ]
        for row in summary["rows"]:
            lines.append(
                f"{row['dataset']} & {row['baseline']} & {row['stream_length']} & "
                f"{row['completed_categories']} & {row['total_rows']} & "
                f"{_format(row['mean_image_auroc'])} \\\\"
            )
        lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    else:
        lines = [
            "\\begin{tabular}{ll}",
            "\\toprule",
            "Status & Detail \\\\",
            "\\midrule",
            "Pending & No completed stream-length sensitivity shards yet \\\\",
            "\\bottomrule",
            "\\end{tabular}",
            "",
        ]
    tex_path.write_text("\n".join(lines))
    return csv_path, json_path, tex_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--tex", type=Path, default=DEFAULT_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize(args.input_root)
    csv_path, json_path, tex_path = write_outputs(
        summary,
        csv_path=args.csv,
        json_path=args.json,
        tex_path=args.tex,
    )
    print(csv_path)
    print(json_path)
    print(tex_path)
    print(
        "status="
        f"{summary['status']} groups={summary['group_count']} "
        f"errors={summary['error_count']} paper_allowed=false claim_allowed=false"
    )
    if summary["error_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
