#!/usr/bin/env python3
"""Repair CRD-lite summaries from existing aggregate metrics without inference.

The historical CRD-lite aggregation matched contaminated rows to epsilon-zero
baselines without seed in the key. This script recomputes CRD-lite with the
current seed-matched implementation, updates aggregate metrics CSV files in
place, rewrites sibling ``crd_lite.csv`` files, and emits an audit JSON.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments import mini_matrix

DEFAULT_INPUT_ROOT = Path("results/latest/paper_candidate")
DEFAULT_AUDIT_JSON = DEFAULT_INPUT_ROOT / "crd_lite_seed_match_audit.json"


class CrdLiteRepairError(ValueError):
    """Raised when CRD-lite repair cannot be completed safely."""


def _metrics_paths(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.glob("**/metrics.csv")
        if "/production_runs/" not in path.as_posix()
    )


def _read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if not rows:
        raise CrdLiteRepairError(f"Metrics CSV has no rows: {path}")
    for required in ["category", "contamination_epsilon", "run_dir", "image_auroc", "aupr"]:
        if required not in fieldnames:
            raise CrdLiteRepairError(f"Missing required column {required!r}: {path}")
    if "crd_lite" not in fieldnames:
        fieldnames.append("crd_lite")
    return rows, fieldnames


def _write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _epsilon_is_zero(row: dict[str, str]) -> bool:
    epsilon = _float_or_none(row.get("contamination_epsilon"))
    return epsilon is not None and math.isclose(epsilon, 0.0, abs_tol=1e-12)


def _nonzero_epsilon_zero_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    bad_rows = []
    for row in rows:
        if not _epsilon_is_zero(row):
            continue
        crd = _float_or_none(row.get("crd_lite"))
        if crd is None or not math.isclose(crd, 0.0, abs_tol=5e-7):
            bad_rows.append(row)
    return bad_rows


def repair(input_root: Path = DEFAULT_INPUT_ROOT) -> dict[str, Any]:
    metric_paths = _metrics_paths(input_root)
    if not metric_paths:
        raise CrdLiteRepairError(f"No aggregate metrics.csv files found under {input_root}")

    repaired_files: list[dict[str, Any]] = []
    before_nonzero_epsilon_zero = 0
    after_nonzero_epsilon_zero = 0
    changed_crd_values = 0
    examples: list[dict[str, Any]] = []

    for metrics_path in metric_paths:
        rows, fieldnames = _read_rows(metrics_path)
        before_bad = _nonzero_epsilon_zero_rows(rows)
        before_nonzero_epsilon_zero += len(before_bad)
        old_by_run_dir = {
            row.get("run_dir", ""): row.get("crd_lite", "") for row in rows if row.get("run_dir")
        }
        category = str(rows[0].get("category") or metrics_path.parent.name)
        crd_rows, crd_by_run_dir = mini_matrix.compute_crd_lite(rows, category=category)
        for row in rows:
            run_dir = row.get("run_dir", "")
            if run_dir in crd_by_run_dir:
                new_value = crd_by_run_dir[run_dir]
                old_value = row.get("crd_lite", "")
                if old_value != new_value:
                    changed_crd_values += 1
                    if len(examples) < 12:
                        examples.append(
                            {
                                "metrics_csv": str(metrics_path),
                                "run_dir": run_dir,
                                "epsilon": row.get("contamination_epsilon"),
                                "old_crd_lite": old_value,
                                "new_crd_lite": new_value,
                            }
                        )
                row["crd_lite"] = new_value
        after_bad = _nonzero_epsilon_zero_rows(rows)
        after_nonzero_epsilon_zero += len(after_bad)
        if after_bad:
            raise CrdLiteRepairError(
                f"Seed-matched CRD-lite still has nonzero epsilon-zero rows in {metrics_path}"
            )
        _write_rows(metrics_path, rows, fieldnames)
        crd_path = metrics_path.parent / "crd_lite.csv"
        mini_matrix.write_crd_lite_summary(crd_path, crd_rows)
        repaired_files.append(
            {
                "metrics_csv": str(metrics_path),
                "crd_lite_csv": str(crd_path),
                "row_count": len(rows),
                "epsilon_zero_nonzero_before": len(before_bad),
                "epsilon_zero_nonzero_after": len(after_bad),
                "changed_rows": sum(
                    1
                    for row in rows
                    if old_by_run_dir.get(row.get("run_dir", "")) != row.get("crd_lite", "")
                ),
            }
        )

    return {
        "status": "crd_lite_seed_matching_repaired",
        "input_root": str(input_root),
        "metrics_file_count": len(metric_paths),
        "changed_crd_values": changed_crd_values,
        "epsilon_zero_nonzero_before": before_nonzero_epsilon_zero,
        "epsilon_zero_nonzero_after": after_nonzero_epsilon_zero,
        "repaired_files": repaired_files,
        "examples": examples,
        "notes": (
            "CRD-lite was recomputed without inference using seed-matched "
            "epsilon-zero baselines. All epsilon-zero CRD-lite rows are required "
            "to be exactly 0.000000 after repair."
        ),
    }


def write_audit(summary: dict[str, Any], path: Path = DEFAULT_AUDIT_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = repair(args.input_root)
    audit_path = write_audit(summary, args.audit_json)
    print(audit_path)
    print(
        "status=crd_lite_seed_matching_repaired "
        f"metrics_files={summary['metrics_file_count']} "
        f"changed_crd_values={summary['changed_crd_values']} "
        f"epsilon_zero_nonzero_before={summary['epsilon_zero_nonzero_before']} "
        f"epsilon_zero_nonzero_after={summary['epsilon_zero_nonzero_after']}"
    )


if __name__ == "__main__":
    main()
