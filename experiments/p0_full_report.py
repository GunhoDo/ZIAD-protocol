#!/usr/bin/env python3
"""Generate a paper-ineligible full-P0 production-validation report."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.render_paper_tables import _latex_escape

DEFAULT_PLAN = Path("results/latest/p0_full/execution_plan.json")
DEFAULT_REPORT = Path("results/latest/p0_full/validation_report.json")
DEFAULT_SUMMARY_CSV = Path("results/latest/tables/p0_full_validation_summary.csv")
DEFAULT_SUMMARY_TEX = Path("results/latest/tables/p0_full_validation_summary.tex")

SUMMARY_FIELDS = [
    "step_id",
    "dataset",
    "baseline",
    "memory_policy",
    "calibration",
    "row_count",
    "expected_row_count",
    "category_count",
    "status_values",
    "stream_length",
    "sampler_percentage",
    "paper_allowed",
    "claim_allowed",
    "review_status",
    "non_finite_metric_count",
    "metrics_csv",
    "manifest_json",
    "crd_lite_csv",
]

class P0FullReportError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise P0FullReportError(f"Missing JSON file: {path}")
    return json.loads(path.read_text())


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise P0FullReportError(f"Missing CSV file: {path}")
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise P0FullReportError(f"No rows found in CSV: {path}")
    return rows


def _expected_row_count(step: dict[str, Any]) -> int:
    validation = step.get("validation", {})
    field = validation.get("expected_row_count_field")
    if not field:
        raise P0FullReportError(f"{step.get('step_id')}: missing expected row count field")
    try:
        return int(step[field])
    except (KeyError, TypeError, ValueError) as error:
        raise P0FullReportError(
            f"{step.get('step_id')}: invalid expected row count from {field!r}"
        ) from error


def _non_finite_metric_count(rows: list[dict[str, str]]) -> int:
    count = 0
    for row in rows:
        for key, value in row.items():
            if key in {"image_auroc", "aupr", "ece", "latency_ms", "crd_lite"}:
                normalized = str(value).strip().lower()
                if normalized in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
                    count += 1
                    continue
                if normalized in {"", "na", "n/a"}:
                    continue
                try:
                    number = float(value)
                except ValueError:
                    continue
                if not math.isfinite(number):
                    count += 1
    return count


def _step_summary(step: dict[str, Any]) -> dict[str, Any]:
    outputs = step.get("outputs", {})
    metrics_path = Path(str(outputs.get("aggregate_metrics", "")))
    manifest_path = Path(str(outputs.get("aggregate_manifest", "")))
    crd_path = Path(str(outputs.get("crd_lite_summary", "")))

    rows = _read_csv(metrics_path)
    manifest = _read_json(manifest_path)
    expected_rows = _expected_row_count(step)
    statuses = sorted({row.get("status", "") for row in rows})
    categories = sorted({row.get("category", "") for row in rows if row.get("category", "")})
    sampler_percentage = manifest.get("production_validation_sampler_percentage")

    return {
        "step_id": step.get("step_id", ""),
        "dataset": step.get("dataset", manifest.get("dataset", "")),
        "baseline": step.get("baseline", manifest.get("baseline", "")),
        "memory_policy": step.get("memory_policy", manifest.get("memory_policy", "")),
        "calibration": step.get("calibration", manifest.get("calibration", "")),
        "row_count": len(rows),
        "expected_row_count": expected_rows,
        "category_count": int(manifest.get("category_count", len(categories))),
        "expected_category_count": int(step.get("category_count", 0)),
        "status_values": statuses,
        "stream_length": manifest.get("stream_length"),
        "sampler_percentage": sampler_percentage,
        "paper_allowed": manifest.get("paper_allowed"),
        "claim_allowed": manifest.get("claim_allowed"),
        "review_status": manifest.get("review_status"),
        "run_tier": manifest.get("run_tier"),
        "execution_mode": manifest.get("execution_mode"),
        "non_finite_metric_count": _non_finite_metric_count(rows),
        "outputs": {
            "metrics_csv": str(metrics_path),
            "manifest_json": str(manifest_path),
            "crd_lite_csv": str(crd_path),
        },
    }


def _paper_promotion_criteria(
    *, stream_lengths: list[str], sampler_percentages: list[str]
) -> list[dict[str, Any]]:
    stream_detail = (
        "Paper promotion requires a reviewed non-validation stream length; "
        f"current validation stream_length values are {stream_lengths}."
    )
    sampler_detail = (
        "Paper promotion requires reviewed sampler and memory settings; "
        f"current validation sampler_percentage values are {sampler_percentages or ['none']}."
    )
    return [
        {
            "criterion": "do_not_promote_validation_runs",
            "required": True,
            "current_status": "blocked",
            "detail": (
                "Current p0_full outputs are production-validation artifacts and must "
                "remain paper_allowed=false and claim_allowed=false."
            ),
        },
        {
            "criterion": "require_non_validation_stream_length",
            "required": True,
            "current_status": "blocked",
            "detail": stream_detail,
        },
        {
            "criterion": "require_paper_sampler_settings",
            "required": True,
            "current_status": "blocked",
            "detail": sampler_detail,
        },
        {
            "criterion": "require_row_count_category_count_checks",
            "required": True,
            "current_status": "must_pass",
            "detail": "Each promoted aggregate must match expected row and category counts.",
        },
        {
            "criterion": "require_no_nan_inf_metrics",
            "required": True,
            "current_status": "must_pass",
            "detail": "Metric cells must not contain NaN, +Inf, or -Inf.",
        },
        {
            "criterion": "require_manual_review",
            "required": True,
            "current_status": "blocked",
            "detail": (
                "A human/manual review must set review_status to an approved state "
                "before paper_allowed or claim_allowed can be considered."
            ),
        },
    ]


def build_report(plan_path: Path = DEFAULT_PLAN) -> dict[str, Any]:
    plan = _read_json(plan_path)
    steps = [_step_summary(step) for step in plan.get("steps", [])]
    if not steps:
        raise P0FullReportError(f"No steps found in plan: {plan_path}")

    row_count_mismatches = [
        step["step_id"]
        for step in steps
        if step["row_count"] != step["expected_row_count"]
    ]
    category_count_mismatches = [
        step["step_id"]
        for step in steps
        if step["category_count"] != step["expected_category_count"]
    ]
    gate_violations = [
        step["step_id"]
        for step in steps
        if step["paper_allowed"] is not False
        or step["claim_allowed"] is not False
        or step["review_status"] != "not_reviewed"
        or step["run_tier"] != "p0_full"
        or step["execution_mode"] != "production"
    ]
    non_finite_steps = [
        step["step_id"] for step in steps if step["non_finite_metric_count"] > 0
    ]
    stream_lengths = sorted({str(step["stream_length"]) for step in steps})
    sampler_percentages = sorted(
        {
            str(step["sampler_percentage"])
            for step in steps
            if step["sampler_percentage"] is not None
        }
    )

    return {
        "status": "p0_full_validation_report_complete",
        "plan": str(plan_path),
        "run_tier": "p0_full",
        "execution_mode": "production",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "not_reviewed",
        "step_count": len(steps),
        "datasets": sorted({str(step["dataset"]) for step in steps}),
        "baselines": sorted({str(step["baseline"]) for step in steps}),
        "memory_policies": sorted({str(step["memory_policy"]) for step in steps}),
        "calibrations": sorted({str(step["calibration"]) for step in steps}),
        "completed_step_count": len(steps)
        - len(set(row_count_mismatches + category_count_mismatches + gate_violations)),
        "row_count_mismatches": row_count_mismatches,
        "category_count_mismatches": category_count_mismatches,
        "gate_violations": gate_violations,
        "non_finite_metric_steps": non_finite_steps,
        "stream_lengths": stream_lengths,
        "sampler_percentages": sampler_percentages,
        "limitations": [
            "Production-validation artifacts only; not paper results.",
            f"Current validation stream_length values are {stream_lengths}.",
            f"Current validation sampler_percentage values are {sampler_percentages or ['none']}.",
            "All outputs remain paper_allowed=false and claim_allowed=false.",
        ],
        "paper_promotion_criteria": _paper_promotion_criteria(
            stream_lengths=stream_lengths,
            sampler_percentages=sampler_percentages,
        ),
        "steps": steps,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


def _csv_row(step: dict[str, Any]) -> dict[str, str]:
    outputs = step["outputs"]
    return {
        "step_id": str(step["step_id"]),
        "dataset": str(step["dataset"]),
        "baseline": str(step["baseline"]),
        "memory_policy": str(step["memory_policy"]),
        "calibration": str(step["calibration"]),
        "row_count": str(step["row_count"]),
        "expected_row_count": str(step["expected_row_count"]),
        "category_count": str(step["category_count"]),
        "status_values": ";".join(step["status_values"]),
        "stream_length": "" if step["stream_length"] is None else str(step["stream_length"]),
        "sampler_percentage": (
            "" if step["sampler_percentage"] is None else str(step["sampler_percentage"])
        ),
        "paper_allowed": str(step["paper_allowed"]).lower(),
        "claim_allowed": str(step["claim_allowed"]).lower(),
        "review_status": str(step["review_status"]),
        "non_finite_metric_count": str(step["non_finite_metric_count"]),
        "metrics_csv": str(outputs["metrics_csv"]),
        "manifest_json": str(outputs["manifest_json"]),
        "crd_lite_csv": str(outputs["crd_lite_csv"]),
    }


def write_summary_csv(path: Path, report: dict[str, Any]) -> None:
    rows = [_csv_row(step) for step in report["steps"]]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def render_summary_table(path: Path, report: dict[str, Any], *, summary_csv: Path) -> str:
    lines = [
        f"% Auto-generated from {summary_csv}.",
        "% Full-P0 production-validation only; paper_allowed=false; claim_allowed=false.",
        "\\begin{table}[t]",
        "\\caption{Full-P0 production-validation summary (not paper results).}",
        "\\label{tab:p0-full-validation-summary}",
        "\\centering",
        "\\begin{tabular}{llllrrrr}",
        "\\hline",
        "Dataset & Baseline & Memory & Calibration & Rows & Expected & Categories & Stream \\\\",
        "\\hline",
    ]
    for step in report["steps"]:
        lines.append(
            " & ".join(
                [
                    _latex_escape(str(step["dataset"])),
                    _latex_escape(str(step["baseline"])),
                    _latex_escape(str(step["memory_policy"])),
                    _latex_escape(str(step["calibration"])),
                    str(step["row_count"]),
                    str(step["expected_row_count"]),
                    str(step["category_count"]),
                    _latex_escape(str(step["stream_length"])),
                ]
            )
            + r" \\"
        )
    lines.extend(
        [
            "\\hline",
            "\\end{tabular}",
            (
                "% Promotion blockers: validation stream length, PatchCore validation "
                "sampler, manual review pending."
            ),
            "\\end{table}",
            "",
        ]
    )
    body = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--tex-output", type=Path, default=DEFAULT_SUMMARY_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.plan)
    write_report(args.report, report)
    write_summary_csv(args.summary_csv, report)
    render_summary_table(args.tex_output, report, summary_csv=args.summary_csv)
    print(args.report)
    print(args.summary_csv)
    print(args.tex_output)
    print(
        "status=p0_full_validation_report_complete "
        f"steps={report['step_count']} "
        f"row_mismatches={len(report['row_count_mismatches'])} "
        f"category_mismatches={len(report['category_count_mismatches'])} "
        f"gate_violations={len(report['gate_violations'])} "
        f"non_finite_steps={len(report['non_finite_metric_steps'])} "
        "paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
