#!/usr/bin/env python3
"""Summarize paper-candidate category-shard coverage for one aggregate step."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow direct script execution.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments import p0_full

DEFAULT_PLAN = Path("results/latest/paper_candidate/execution_plan.json")


class SummaryError(ValueError):
    """Raised when paper-candidate summary inputs are malformed."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SummaryError(f"Missing JSON file: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SummaryError(f"JSON file must contain an object: {path}")
    return payload


def _resolve_step(plan: dict[str, Any], step_id: str) -> dict[str, Any]:
    for step in plan.get("steps", []):
        if isinstance(step, dict) and step.get("step_id") == step_id:
            return step
    raise SummaryError(f"Unknown paper-candidate step id: {step_id}")


def _read_metrics(path: Path) -> tuple[int, list[str]]:
    if not path.exists():
        return 0, []
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return len(rows), sorted({str(row.get("status", "")) for row in rows})


def _category_root(step: dict[str, Any], category: str) -> Path:
    return Path(str(step["output_root"])) / p0_full._slug(category)


def summarize_step(plan: dict[str, Any], step_id: str) -> dict[str, Any]:
    step = _resolve_step(plan, step_id)
    categories = [str(value) for value in step.get("categories", [])]
    expected_rows = int(step.get("expected_category_shard_run_count") or 12)
    rows: list[dict[str, Any]] = []
    complete_count = 0

    for category in categories:
        root = _category_root(step, category)
        metrics_path = root / "metrics.csv"
        manifest_path = root / "manifest.json"
        crd_path = root / "crd_lite.csv"
        row_count, statuses = _read_metrics(metrics_path)
        manifest = _load_json(manifest_path) if manifest_path.exists() else {}
        complete = (
            metrics_path.exists()
            and manifest_path.exists()
            and crd_path.exists()
            and row_count == expected_rows
            and statuses == ["measured_paper_candidate"]
            and manifest.get("candidate_scope") == "category_shard"
            and manifest.get("category") == category
            and manifest.get("category_count") == 1
            and manifest.get("paper_allowed") is False
            and manifest.get("claim_allowed") is False
            and manifest.get("review_status") == "review_pending"
        )
        if complete:
            complete_count += 1
        rows.append(
            {
                "category": category,
                "complete": complete,
                "row_count": row_count,
                "expected_row_count": expected_rows,
                "status_values": statuses,
                "category_count": manifest.get("category_count"),
                "stream_length": manifest.get("stream_length"),
                "seeds": manifest.get("seeds"),
                "candidate_scope": manifest.get("candidate_scope"),
                "paper_allowed": manifest.get("paper_allowed"),
                "claim_allowed": manifest.get("claim_allowed"),
                "review_status": manifest.get("review_status"),
                "metrics_csv": str(metrics_path),
                "manifest_json": str(manifest_path),
                "crd_lite_csv": str(crd_path),
            }
        )

    return {
        "status": (
            "category_shards_complete"
            if complete_count == len(categories)
            else "category_shards_incomplete"
        ),
        "run_tier": "paper_candidate",
        "candidate_scope": "category_shard_set",
        "step_id": step_id,
        "dataset": step.get("dataset"),
        "baseline": step.get("baseline"),
        "memory_policy": step.get("memory_policy"),
        "calibration": step.get("calibration"),
        "category_count": len(categories),
        "complete_category_count": complete_count,
        "pending_category_count": len(categories) - complete_count,
        "expected_row_count_per_category": expected_rows,
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "output_root": step.get("output_root"),
        "categories": rows,
        "notes": (
            "Paper-candidate category-shard set only. This summary is not a "
            "paper result and does not promote paper_allowed or claim_allowed."
        ),
    }


def write_summary(summary: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "category_summary.json"
    csv_path = output_root / "category_summary.csv"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    fieldnames = [
        "category",
        "complete",
        "row_count",
        "expected_row_count",
        "status_values",
        "category_count",
        "stream_length",
        "seeds",
        "candidate_scope",
        "paper_allowed",
        "claim_allowed",
        "review_status",
        "metrics_csv",
        "manifest_json",
        "crd_lite_csv",
    ]
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in summary["categories"]:
            serializable = dict(row)
            serializable["status_values"] = "|".join(row["status_values"])
            serializable["seeds"] = "|".join(str(value) for value in (row["seeds"] or []))
            writer.writerow(serializable)
    return csv_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--output-root", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = _load_json(args.plan)
    summary = summarize_step(plan, args.step_id)
    output_root = args.output_root or Path(str(summary["output_root"]))
    csv_path, json_path = write_summary(summary, output_root)
    print(csv_path)
    print(json_path)
    print(
        "status="
        f"{summary['status']} complete={summary['complete_category_count']}/"
        f"{summary['category_count']} paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
