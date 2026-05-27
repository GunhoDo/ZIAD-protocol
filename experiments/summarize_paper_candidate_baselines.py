#!/usr/bin/env python3
"""Summarize completed paper-candidate category-shard sets by baseline."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_INPUT_ROOT = Path("results/latest/paper_candidate/mvtec_ad")
DEFAULT_OUTPUT_CSV = DEFAULT_INPUT_ROOT / "baseline_comparison_none.csv"
DEFAULT_OUTPUT_JSON = DEFAULT_INPUT_ROOT / "baseline_comparison_none.json"
DEFAULT_OUTPUT_TEX = Path("results/latest/tables/paper_candidate_mvtec_baseline_comparison_none.tex")
DEFAULT_BASELINE_SPECS = [
    ("winclip", "default_no_memory"),
    ("anomalyclip", "default_no_memory"),
    ("rareclip", "default_scs"),
    ("patchcore", "default_scs"),
]
METRIC_COLUMNS = ["image_auroc", "aupr", "ece", "latency_ms", "crd_lite"]


class BaselineSummaryError(ValueError):
    """Raised when paper-candidate baseline summary inputs are invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise BaselineSummaryError(f"Missing JSON file: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise BaselineSummaryError(f"JSON file must contain an object: {path}")
    return payload


def _parse_float(value: Any) -> float | None:
    if value in {None, "", "NA"}:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _read_metric_rows(summary: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for category in summary.get("categories", []):
        if not category.get("complete"):
            continue
        metrics_path = Path(str(category.get("metrics_csv", "")))
        if not metrics_path.exists():
            raise BaselineSummaryError(f"Missing category metrics CSV: {metrics_path}")
        with metrics_path.open(newline="") as handle:
            rows.extend(dict(row) for row in csv.DictReader(handle))
    return rows


def _validate_summary(summary: dict[str, Any], *, path: Path) -> None:
    if summary.get("status") != "category_shards_complete":
        raise BaselineSummaryError(f"Category summary is not complete: {path}")
    if summary.get("paper_allowed") is not False:
        raise BaselineSummaryError(f"Category summary paper_allowed must be false: {path}")
    if summary.get("claim_allowed") is not False:
        raise BaselineSummaryError(f"Category summary claim_allowed must be false: {path}")
    if summary.get("review_status") != "review_pending":
        raise BaselineSummaryError(f"Category summary review_status must be review_pending: {path}")


def _summary_path(root: Path, baseline: str, memory_policy: str, calibration: str) -> Path:
    return root / baseline / memory_policy / calibration / "category_summary.json"


def _baseline_specs(
    baselines: list[str] | None,
    *,
    memory_policy: str,
) -> list[tuple[str, str]]:
    if not baselines:
        return list(DEFAULT_BASELINE_SPECS)
    specs: list[tuple[str, str]] = []
    for baseline in baselines:
        if ":" in baseline:
            baseline_slug, baseline_memory_policy = baseline.split(":", 1)
            if not baseline_slug or not baseline_memory_policy:
                raise BaselineSummaryError(
                    f"Baseline spec must be '<baseline>' or '<baseline>:<memory_policy>': {baseline}"
                )
            specs.append((baseline_slug, baseline_memory_policy))
        else:
            specs.append((baseline, memory_policy))
    return specs


def summarize_baselines(
    *,
    input_root: Path = DEFAULT_INPUT_ROOT,
    baselines: list[str] | None = None,
    memory_policy: str = "default_no_memory",
    calibration: str = "none",
) -> dict[str, Any]:
    baseline_specs = _baseline_specs(baselines, memory_policy=memory_policy)
    rows: list[dict[str, Any]] = []
    datasets: set[str] = set()
    for baseline_slug, baseline_memory_policy in baseline_specs:
        path = _summary_path(input_root, baseline_slug, baseline_memory_policy, calibration)
        summary = _load_json(path)
        _validate_summary(summary, path=path)
        dataset = str(summary.get("dataset", ""))
        if not dataset:
            raise BaselineSummaryError(f"Category summary dataset is missing: {path}")
        datasets.add(dataset)
        metric_rows = _read_metric_rows(summary)
        if not metric_rows:
            raise BaselineSummaryError(f"No metric rows found for baseline summary: {path}")

        status_values = sorted({str(row.get("status", "")) for row in metric_rows})
        if status_values != ["measured_paper_candidate"]:
            raise BaselineSummaryError(
                f"Unexpected metric status values for {path}: {status_values}"
            )

        metric_means: dict[str, float | None] = {}
        for column in METRIC_COLUMNS:
            values = [
                parsed
                for parsed in (_parse_float(row.get(column)) for row in metric_rows)
                if parsed is not None
            ]
            metric_means[f"mean_{column}"] = _mean(values)

        stream_lengths = sorted(
            {int(category["stream_length"]) for category in summary.get("categories", [])}
        )
        seeds = sorted(
            {
                int(seed)
                for category in summary.get("categories", [])
                for seed in (category.get("seeds") or [])
            }
        )
        rows.append(
            {
                "dataset": summary.get("dataset"),
                "baseline": summary.get("baseline"),
                "memory_policy": summary.get("memory_policy"),
                "calibration": summary.get("calibration"),
                "completed_categories": int(summary.get("complete_category_count", 0)),
                "expected_categories": int(summary.get("category_count", 0)),
                "total_rows": len(metric_rows),
                "stream_length": "|".join(str(value) for value in stream_lengths),
                "seeds": "|".join(str(value) for value in seeds),
                "paper_allowed": False,
                "claim_allowed": False,
                "review_status": "review_pending",
                "status_values": "|".join(status_values),
                "category_summary_json": str(path),
                **metric_means,
            }
        )

    if len(datasets) != 1:
        raise BaselineSummaryError(
            f"Baseline comparison requires one dataset, got: {sorted(datasets)}"
        )
    dataset = next(iter(datasets))
    return {
        "status": "paper_candidate_baseline_comparison_complete",
        "run_tier": "paper_candidate",
        "candidate_scope": "baseline_comparison",
        "dataset": dataset,
        "calibration": calibration,
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "baseline_count": len(rows),
        "baselines": rows,
        "notes": (
            "Paper-candidate baseline comparison only. These category-shard "
            "sets are review-pending and do not promote paper_allowed or "
            "claim_allowed."
        ),
    }


def _format_value(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_csv(summary: dict[str, Any], path: Path) -> None:
    rows = summary["baselines"]
    if not rows:
        raise BaselineSummaryError("No baseline rows to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _format_value(value) for key, value in row.items()})


def write_json(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")


def _tex_escape(value: Any) -> str:
    text = _format_value(value)
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


def write_tex(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        ("baseline", "Baseline"),
        ("completed_categories", "Categories"),
        ("total_rows", "Rows"),
        ("stream_length", "Length"),
        ("seeds", "Seeds"),
        ("mean_image_auroc", "AUROC"),
        ("mean_aupr", "AUPR"),
        ("mean_ece", "ECE"),
        ("mean_latency_ms", "Latency ms"),
        ("mean_crd_lite", "CRD-lite"),
    ]
    lines = [
        "% Auto-generated paper-candidate table. Not a final paper result.",
        "\\begin{tabular}{lrrrrrrrrr}",
        "\\toprule",
        " & ".join(label for _, label in columns) + r" \\",
        "\\midrule",
    ]
    for row in summary["baselines"]:
        values = []
        for key, _ in columns:
            value = row.get(key)
            if key == "completed_categories":
                value = f"{row.get('completed_categories')}/{row.get('expected_categories')}"
            values.append(_tex_escape(value))
        lines.append(" & ".join(values) + r" \\")
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "% paper_allowed=false; claim_allowed=false; review_status=review_pending",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def write_outputs(
    summary: dict[str, Any],
    *,
    csv_path: Path = DEFAULT_OUTPUT_CSV,
    json_path: Path = DEFAULT_OUTPUT_JSON,
    tex_path: Path = DEFAULT_OUTPUT_TEX,
) -> tuple[Path, Path, Path]:
    write_csv(summary, csv_path)
    write_json(summary, json_path)
    write_tex(summary, tex_path)
    return csv_path, json_path, tex_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--baseline", action="append", dest="baselines")
    parser.add_argument("--memory-policy", default="default_no_memory")
    parser.add_argument("--calibration", default="none")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize_baselines(
        input_root=args.input_root,
        baselines=args.baselines,
        memory_policy=args.memory_policy,
        calibration=args.calibration,
    )
    csv_path, json_path, tex_path = write_outputs(
        summary,
        csv_path=args.output_csv,
        json_path=args.output_json,
        tex_path=args.output_tex,
    )
    print(csv_path)
    print(json_path)
    print(tex_path)
    print(
        "status="
        f"{summary['status']} baselines={summary['baseline_count']} "
        "paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
