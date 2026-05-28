#!/usr/bin/env python3
"""Audit review-pending paper-candidate metric tables before claim promotion."""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_COMBINED_CSV = Path(
    "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv"
)
DEFAULT_OUTPUT_JSON = Path("results/latest/paper_candidate/metric_audit_report.json")
DEFAULT_OUTPUT_TEX = Path("results/latest/tables/paper_candidate_metric_audit_summary.tex")
DEFAULT_CATEGORY_SUMMARY_GLOB = (
    "results/latest/paper_candidate/*/*/*/none/category_summary.json"
)

EXPECTED_DATASETS = {"MVTec AD", "VisA"}
EXPECTED_BASELINES = {"PatchCore", "WinCLIP", "AnomalyCLIP", "RareCLIP"}
EXPECTED_ROW_COUNT = 8

REQUIRED_COLUMNS = [
    "dataset",
    "baseline",
    "memory_policy",
    "calibration",
    "completed_categories",
    "expected_categories",
    "total_rows",
    "stream_length",
    "seeds",
    "mean_image_auroc",
    "mean_aupr",
    "mean_ece",
    "mean_latency_ms",
    "mean_crd_lite",
    "paper_allowed",
    "claim_allowed",
    "review_status",
]

NUMERIC_COLUMNS = [
    "completed_categories",
    "expected_categories",
    "total_rows",
    "stream_length",
    "mean_image_auroc",
    "mean_aupr",
    "mean_ece",
    "mean_latency_ms",
    "mean_crd_lite",
]


class MetricAuditError(ValueError):
    """Raised when paper-candidate metrics fail the closed-gate audit."""


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized == "false":
        return False
    if normalized == "true":
        return True
    return None


def _parse_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    if not path.exists():
        return [], [f"Missing combined CSV: {path}"]
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing_columns:
            errors.append(f"Missing required columns in {path}: {missing_columns}")
        rows = [dict(row) for row in reader]
    if not rows:
        errors.append(f"No metric rows found in {path}")
    return rows, errors


def _audit_combined_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    missing_values: list[dict[str, Any]] = []
    non_finite_values: list[dict[str, Any]] = []
    negative_latency_rows: list[dict[str, Any]] = []

    if len(rows) != EXPECTED_ROW_COUNT:
        errors.append(f"Expected {EXPECTED_ROW_COUNT} rows, found {len(rows)}")

    datasets = sorted({row.get("dataset", "") for row in rows})
    if set(datasets) != EXPECTED_DATASETS:
        errors.append(f"Expected datasets {sorted(EXPECTED_DATASETS)}, found {datasets}")

    baselines_by_dataset: dict[str, list[str]] = {}
    for dataset in datasets:
        baselines = sorted({row.get("baseline", "") for row in rows if row.get("dataset") == dataset})
        baselines_by_dataset[dataset] = baselines
        if set(baselines) != EXPECTED_BASELINES:
            errors.append(
                f"Expected baselines {sorted(EXPECTED_BASELINES)} for {dataset}, found {baselines}"
            )

    for index, row in enumerate(rows):
        row_id = {
            "row_index": index,
            "dataset": row.get("dataset"),
            "baseline": row.get("baseline"),
        }
        for column in REQUIRED_COLUMNS:
            value = row.get(column)
            if value is None or str(value).strip() == "":
                missing_values.append({**row_id, "column": column})
        for column in NUMERIC_COLUMNS:
            value = row.get(column)
            parsed = _parse_float(value)
            if parsed is None:
                non_finite_values.append({**row_id, "column": column, "value": value})
            elif column == "mean_latency_ms" and parsed < 0:
                negative_latency_rows.append({**row_id, "value": parsed})
        paper_allowed = _parse_bool(row.get("paper_allowed"))
        claim_allowed = _parse_bool(row.get("claim_allowed"))
        if paper_allowed is not False:
            errors.append(f"paper_allowed must be false at row {index}")
        if claim_allowed is not False:
            errors.append(f"claim_allowed must be false at row {index}")
        if row.get("review_status") != "review_pending":
            errors.append(f"review_status must be review_pending at row {index}")

    if missing_values:
        errors.append(f"Missing values found: {len(missing_values)}")
    if non_finite_values:
        errors.append(f"NaN/Inf or non-numeric values found: {len(non_finite_values)}")
    if negative_latency_rows:
        errors.append(f"Negative latency rows found: {len(negative_latency_rows)}")

    return {
        "row_count": len(rows),
        "dataset_count": len(datasets),
        "datasets": datasets,
        "baseline_count_by_dataset": {
            dataset: len(baselines) for dataset, baselines in baselines_by_dataset.items()
        },
        "baselines_by_dataset": baselines_by_dataset,
        "missing_value_count": len(missing_values),
        "missing_values": missing_values,
        "non_finite_value_count": len(non_finite_values),
        "non_finite_values": non_finite_values,
        "negative_latency_count": len(negative_latency_rows),
        "negative_latency_rows": negative_latency_rows,
        "warnings": warnings,
        "errors": errors,
    }


def _load_category_summaries(pattern: str | None) -> tuple[list[dict[str, Any]], list[str]]:
    if not pattern:
        return [], []
    summaries: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw_path in sorted(glob.glob(pattern)):
        path = Path(raw_path)
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid category summary JSON {path}: {exc}")
            continue
        summaries.append({"path": str(path), "payload": payload})
        if payload.get("status") != "category_shards_complete":
            errors.append(f"Category summary is not complete: {path}")
        if payload.get("paper_allowed") is not False:
            errors.append(f"Category summary paper_allowed must be false: {path}")
        if payload.get("claim_allowed") is not False:
            errors.append(f"Category summary claim_allowed must be false: {path}")
        if payload.get("review_status") != "review_pending":
            errors.append(f"Category summary review_status must be review_pending: {path}")
    return summaries, errors


def build_metric_audit(
    *,
    combined_csv: Path = DEFAULT_COMBINED_CSV,
    category_summary_glob: str | None = DEFAULT_CATEGORY_SUMMARY_GLOB,
) -> dict[str, Any]:
    rows, read_errors = _read_rows(combined_csv)
    combined = _audit_combined_rows(rows) if rows else {
        "row_count": 0,
        "dataset_count": 0,
        "datasets": [],
        "baseline_count_by_dataset": {},
        "baselines_by_dataset": {},
        "missing_value_count": 0,
        "missing_values": [],
        "non_finite_value_count": 0,
        "non_finite_values": [],
        "negative_latency_count": 0,
        "negative_latency_rows": [],
        "warnings": [],
        "errors": [],
    }
    category_summaries, category_errors = _load_category_summaries(category_summary_glob)
    errors = read_errors + list(combined["errors"]) + category_errors
    status = "paper_candidate_metric_audit_passed" if not errors else "paper_candidate_metric_audit_failed"
    return {
        "status": status,
        "run_tier": "paper_candidate",
        "candidate_scope": "metric_audit",
        "source_csv": str(combined_csv),
        "category_summary_glob": category_summary_glob,
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "expected_dataset_count": len(EXPECTED_DATASETS),
        "expected_baseline_count_per_dataset": len(EXPECTED_BASELINES),
        "expected_row_count": EXPECTED_ROW_COUNT,
        "combined_csv": combined,
        "category_summary_count": len(category_summaries),
        "category_summaries": [
            {
                "path": item["path"],
                "status": item["payload"].get("status"),
                "dataset": item["payload"].get("dataset"),
                "baseline": item["payload"].get("baseline"),
                "complete_category_count": item["payload"].get("complete_category_count"),
                "category_count": item["payload"].get("category_count"),
                "paper_allowed": item["payload"].get("paper_allowed"),
                "claim_allowed": item["payload"].get("claim_allowed"),
                "review_status": item["payload"].get("review_status"),
            }
            for item in category_summaries
        ],
        "error_count": len(errors),
        "errors": errors,
        "notes": (
            "Audit covers review-pending paper-candidate summary metrics only. "
            "Passing this audit does not promote paper_allowed or claim_allowed."
        ),
    }


def write_json(report: dict[str, Any], path: Path = DEFAULT_OUTPUT_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return path


def _tex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def write_tex(report: dict[str, Any], path: Path = DEFAULT_OUTPUT_TEX) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("Status", report["status"]),
        ("Rows", f"{report['combined_csv']['row_count']}/{report['expected_row_count']}"),
        ("Datasets", f"{report['combined_csv']['dataset_count']}/{report['expected_dataset_count']}"),
        ("Missing values", report["combined_csv"]["missing_value_count"]),
        ("NaN/Inf values", report["combined_csv"]["non_finite_value_count"]),
        ("Negative latency rows", report["combined_csv"]["negative_latency_count"]),
        ("Category summaries", report["category_summary_count"]),
        ("Errors", report["error_count"]),
    ]
    lines = [
        "% Auto-generated paper-candidate metric audit. Not a final paper result.",
        "\\begin{tabular}{lr}",
        "\\toprule",
        "Check & Value \\\\",
        "\\midrule",
    ]
    for label, value in rows:
        lines.append(f"{_tex_escape(label)} & {_tex_escape(value)} \\\\")
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "% paper_allowed=false; claim_allowed=false; review_status=review_pending",
            "",
        ]
    )
    path.write_text("\n".join(lines))
    return path


def write_outputs(
    report: dict[str, Any],
    *,
    json_path: Path = DEFAULT_OUTPUT_JSON,
    tex_path: Path = DEFAULT_OUTPUT_TEX,
) -> tuple[Path, Path]:
    return write_json(report, json_path), write_tex(report, tex_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-csv", type=Path, default=DEFAULT_COMBINED_CSV)
    parser.add_argument("--category-summary-glob", default=DEFAULT_CATEGORY_SUMMARY_GLOB)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_metric_audit(
        combined_csv=args.combined_csv,
        category_summary_glob=args.category_summary_glob,
    )
    json_path, tex_path = write_outputs(
        report,
        json_path=args.output_json,
        tex_path=args.output_tex,
    )
    print(json_path)
    print(tex_path)
    print(f"status={report['status']} errors={report['error_count']}")
    if report["error_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
