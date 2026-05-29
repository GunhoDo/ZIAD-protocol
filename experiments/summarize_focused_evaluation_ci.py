#!/usr/bin/env python3
"""Compute bootstrap confidence intervals for the focused evaluation slice.

This script reads existing paper-candidate category-shard metrics and does not
run inference. Bootstrap units are category/seed strata: each stratum first
averages over the available stream/epsilon rows, then the script resamples
strata with replacement to estimate uncertainty for each dataset/baseline pair.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_INPUT_ROOT = Path("results/latest/paper_candidate")
DEFAULT_OUTPUT_JSON = DEFAULT_INPUT_ROOT / "focused_evaluation_ci_summary.json"
DEFAULT_OUTPUT_TEX = Path("results/latest/tables/focused_evaluation_ci_summary.tex")

METRIC_COLUMNS = ["image_auroc", "aupr", "ece", "latency_ms", "crd_lite"]
REQUIRED_COLUMNS = {
    "dataset",
    "baseline",
    "memory_policy",
    "calibration",
    "category",
    "run_dir",
    "status",
    *METRIC_COLUMNS,
}
SUMMARY_COLUMNS = [
    "dataset",
    "baseline",
    "memory_policy",
    "calibration",
    "category_count",
    "seed_count",
    "metric_row_count",
    "stratum_count",
    "mean_image_auroc",
    "ci95_low_image_auroc",
    "ci95_high_image_auroc",
    "mean_aupr",
    "ci95_low_aupr",
    "ci95_high_aupr",
    "mean_ece",
    "ci95_low_ece",
    "ci95_high_ece",
    "mean_latency_ms",
    "ci95_low_latency_ms",
    "ci95_high_latency_ms",
    "mean_crd_lite",
    "ci95_low_crd_lite",
    "ci95_high_crd_lite",
]


class FocusedEvaluationCIError(ValueError):
    """Raised when focused-evaluation CI inputs are incomplete or invalid."""


def _parse_float(value: Any, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise FocusedEvaluationCIError(f"Invalid numeric value for {field}: {value!r}") from exc
    if not math.isfinite(parsed):
        raise FocusedEvaluationCIError(f"Non-finite numeric value for {field}: {value!r}")
    return parsed


def _mean(values: list[float]) -> float:
    if not values:
        raise FocusedEvaluationCIError("Cannot compute mean over an empty list")
    return sum(values) / len(values)


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise FocusedEvaluationCIError("Cannot compute percentile over an empty list")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _parse_seed(row: dict[str, str]) -> str:
    run_dir = row.get("run_dir", "")
    match = re.search(r"_seed_([^/]+)", run_dir)
    if match:
        return match.group(1)
    raise FocusedEvaluationCIError(f"Cannot parse seed from run_dir: {run_dir!r}")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FocusedEvaluationCIError(f"Missing JSON file: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise FocusedEvaluationCIError(f"Expected JSON object: {path}")
    return payload


def _validate_category_summary(summary: dict[str, Any], *, path: Path) -> None:
    if summary.get("status") != "category_shards_complete":
        raise FocusedEvaluationCIError(f"Category summary is not complete: {path}")
    if summary.get("paper_allowed") is not False:
        raise FocusedEvaluationCIError(f"paper_allowed must be false: {path}")
    if summary.get("claim_allowed") is not False:
        raise FocusedEvaluationCIError(f"claim_allowed must be false: {path}")
    if summary.get("review_status") != "review_pending":
        raise FocusedEvaluationCIError(f"review_status must be review_pending: {path}")


def _read_metric_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FocusedEvaluationCIError(f"Missing metrics CSV: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))
        if missing:
            raise FocusedEvaluationCIError(f"Missing metric columns in {path}: {missing}")
        rows = list(reader)
    if not rows:
        raise FocusedEvaluationCIError(f"Metrics CSV has no rows: {path}")
    for row in rows:
        if row.get("status") != "measured_paper_candidate":
            raise FocusedEvaluationCIError(
                f"Unexpected metric status in {path}: {row.get('status')}"
            )
        for column in METRIC_COLUMNS:
            _parse_float(row.get(column), field=column)
        _parse_seed(row)
    return rows


def _summary_paths(input_root: Path) -> list[Path]:
    return sorted(input_root.glob("*/*/*/none/category_summary.json"))


def _strata_from_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_stratum: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_stratum[(row["category"], _parse_seed(row))].append(row)

    strata: list[dict[str, Any]] = []
    for (category, seed), stratum_rows in sorted(by_stratum.items()):
        strata.append(
            {
                "category": category,
                "seed": seed,
                **{
                    column: _mean(
                        [_parse_float(row[column], field=column) for row in stratum_rows]
                    )
                    for column in METRIC_COLUMNS
                },
            }
        )
    return strata


def _bootstrap_ci(
    strata: list[dict[str, Any]],
    metric: str,
    *,
    iterations: int,
    rng: random.Random,
) -> tuple[float, float, float]:
    values = [float(stratum[metric]) for stratum in strata]
    observed = _mean(values)
    if len(values) == 1 or iterations <= 0:
        return observed, observed, observed
    estimates = []
    for _ in range(iterations):
        sample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(_mean(sample))
    estimates.sort()
    return observed, _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def summarize_ci(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    iterations: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    summaries = _summary_paths(input_root)
    if not summaries:
        raise FocusedEvaluationCIError(f"No category summaries found under {input_root}")

    output_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    rng = random.Random(seed)

    for summary_path in summaries:
        category_summary = _load_json(summary_path)
        _validate_category_summary(category_summary, path=summary_path)
        metric_rows: list[dict[str, str]] = []
        for category in category_summary.get("categories", []):
            if not category.get("complete"):
                raise FocusedEvaluationCIError(f"Incomplete category in {summary_path}")
            metric_rows.extend(_read_metric_rows(Path(category["metrics_csv"])))

        strata = _strata_from_rows(metric_rows)
        categories = sorted({stratum["category"] for stratum in strata})
        seeds = sorted({stratum["seed"] for stratum in strata})
        if len(strata) < 6:
            warnings.append(
                f"{category_summary.get('dataset')}|{category_summary.get('baseline')} "
                f"has only {len(strata)} bootstrap strata"
            )

        row: dict[str, Any] = {
            "dataset": category_summary["dataset"],
            "baseline": category_summary["baseline"],
            "memory_policy": category_summary["memory_policy"],
            "calibration": category_summary["calibration"],
            "category_count": len(categories),
            "seed_count": len(seeds),
            "metric_row_count": len(metric_rows),
            "stratum_count": len(strata),
        }
        for metric in METRIC_COLUMNS:
            mean, low, high = _bootstrap_ci(
                strata,
                metric,
                iterations=iterations,
                rng=rng,
            )
            row[f"mean_{metric}"] = mean
            row[f"ci95_low_{metric}"] = low
            row[f"ci95_high_{metric}"] = high
        output_rows.append(row)

    output_rows.sort(key=lambda row: (row["dataset"], row["baseline"]))
    dataset_count = len({row["dataset"] for row in output_rows})
    baseline_count = len(output_rows)
    return {
        "status": "focused_evaluation_ci_complete",
        "run_tier": "paper_candidate",
        "candidate_scope": "focused_evaluation_ci",
        "bootstrap_unit": "category_seed_stratum",
        "bootstrap_iterations": iterations,
        "bootstrap_seed": seed,
        "dataset_count": dataset_count,
        "baseline_row_count": baseline_count,
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "warnings": warnings,
        "rows": output_rows,
        "notes": (
            "No-inference stratified bootstrap summary over existing focused "
            "evaluation category shards. Intervals quantify local uncertainty "
            "for the focused slice only."
        ),
    }


def _format_float(value: Any, *, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}"


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


def _ci_text(row: dict[str, Any], metric: str, *, digits: int = 3) -> str:
    mean = _format_float(row[f"mean_{metric}"], digits=digits)
    low = _format_float(row[f"ci95_low_{metric}"], digits=digits)
    high = _format_float(row[f"ci95_high_{metric}"], digits=digits)
    return f"{mean} [{low}, {high}]"


def write_json(summary: dict[str, Any], path: Path = DEFAULT_OUTPUT_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return path


def write_tex(summary: dict[str, Any], path: Path = DEFAULT_OUTPUT_TEX) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "% Auto-generated focused-evaluation bootstrap CI table.",
        "\\begin{tabular}{@{}l@{\\hspace{0.7em}}l@{\\hspace{0.7em}}c@{\\hspace{0.7em}}lll@{}}",
        "\\toprule",
        "Dataset & Baseline & Strata & AUROC 95\\% CI & ECE 95\\% CI & Lat. 95\\% CI \\\\",
        "\\midrule",
    ]
    previous_dataset = None
    for row in summary["rows"]:
        dataset = row["dataset"]
        if previous_dataset is not None and dataset != previous_dataset:
            lines.append("\\addlinespace[0.18em]")
        previous_dataset = dataset
        values = [
            _tex_escape(dataset),
            _tex_escape(row["baseline"]),
            str(row["stratum_count"]),
            _ci_text(row, "image_auroc"),
            _ci_text(row, "ece"),
            _ci_text(row, "latency_ms", digits=1),
        ]
        lines.append(" & ".join(values) + r" \\")
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n")
    return path


def write_outputs(
    summary: dict[str, Any],
    *,
    json_path: Path = DEFAULT_OUTPUT_JSON,
    tex_path: Path = DEFAULT_OUTPUT_TEX,
) -> tuple[Path, Path]:
    return write_json(summary, json_path), write_tex(summary, tex_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize_ci(
        input_root=args.input_root,
        iterations=args.iterations,
        seed=args.seed,
    )
    json_path, tex_path = write_outputs(
        summary,
        json_path=args.output_json,
        tex_path=args.output_tex,
    )
    print(json_path)
    print(tex_path)
    print(
        "status="
        f"{summary['status']} rows={summary['baseline_row_count']} "
        f"warnings={len(summary['warnings'])} paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
