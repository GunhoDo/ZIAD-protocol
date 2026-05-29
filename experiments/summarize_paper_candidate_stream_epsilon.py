#!/usr/bin/env python3
"""Summarize paper-candidate metrics by stream type and contamination epsilon."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_INPUT_ROOT = Path("results/latest/paper_candidate")
DEFAULT_OUTPUT_CSV = DEFAULT_INPUT_ROOT / "stream_epsilon_breakdown_none.csv"
DEFAULT_OUTPUT_JSON = DEFAULT_INPUT_ROOT / "stream_epsilon_breakdown_none.json"
DEFAULT_OUTPUT_TEX = Path(
    "results/latest/tables/paper_candidate_stream_epsilon_breakdown_none.tex"
)

EXPECTED_DATASETS = {
    "mvtec_ad": ("MVTec AD", 15),
    "visa": ("VisA", 12),
}
EXPECTED_BASELINES = {
    "winclip": ("WinCLIP", "default_no_memory", "default/no-memory"),
    "anomalyclip": ("AnomalyCLIP", "default_no_memory", "default/no-memory"),
    "rareclip": ("RareCLIP", "default_scs", "default/SCS"),
    "patchcore": ("PatchCore", "default_scs", "default/SCS"),
}
EXPECTED_STREAM_TYPES = {"iid", "bursty"}
EXPECTED_EPSILONS = {"0", "0.05"}
METRIC_COLUMNS = ["image_auroc", "aupr", "ece", "latency_ms", "crd_lite"]
REQUIRED_METRIC_COLUMNS = {
    "dataset",
    "stream_type",
    "contamination_epsilon",
    "baseline",
    "memory_policy",
    "calibration",
    "category",
    "status",
    *METRIC_COLUMNS,
}
OUTPUT_COLUMNS = [
    "dataset",
    "baseline",
    "memory_policy",
    "calibration",
    "stream_type",
    "epsilon",
    "row_count",
    "category_count",
    "seed_count",
    "mean_image_auroc",
    "mean_aupr",
    "mean_ece",
    "mean_latency_ms",
    "mean_crd_lite",
    "paper_allowed",
    "claim_allowed",
    "review_status",
]
COMPACT_TEX_COLUMNS = [
    ("dataset", "Dataset"),
    ("baseline", "Baseline"),
    ("mean_image_auroc", "AUROC"),
    ("delta_bursty_iid_auroc", "$\\Delta$B-I"),
    ("delta_eps_0p05_0_auroc", "$\\Delta\\epsilon$"),
    ("delta_eps_0p05_0_ece", "$\\Delta$ECE"),
    ("mean_latency_ms", "Lat. ms"),
]


class StreamEpsilonSummaryError(ValueError):
    """Raised when stream/epsilon summary inputs are incomplete or invalid."""


def _parse_float(value: Any, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise StreamEpsilonSummaryError(f"Invalid numeric value for {field}: {value!r}") from exc
    if not math.isfinite(parsed):
        raise StreamEpsilonSummaryError(f"Non-finite numeric value for {field}: {value!r}")
    return parsed


def _mean(values: list[float]) -> float:
    if not values:
        raise StreamEpsilonSummaryError("Cannot compute mean over an empty list")
    return sum(values) / len(values)


def _format_float(value: float) -> str:
    return f"{value:.6f}"


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return _format_float(value)
    if isinstance(value, bool):
        return "False" if value is False else "True"
    return str(value)


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


def _tex_value(row: dict[str, Any], key: str) -> str:
    value = row.get(key, "")
    if key == "stream_type":
        return "IID" if value == "iid" else "Bursty"
    if key == "mean_latency_ms":
        return f"{float(value):.1f}"
    if key.startswith("mean_"):
        return f"{float(value):.3f}"
    return _tex_escape(value)


def _compact_tex_value(row: dict[str, Any], key: str) -> str:
    value = row.get(key, "")
    if key == "mean_latency_ms":
        return f"{float(value):.1f}"
    if key.startswith("mean_") or key.startswith("delta_"):
        return f"{float(value):+.3f}" if key.startswith("delta_") else f"{float(value):.3f}"
    return _tex_escape(value)


def _epsilon_key(value: Any) -> str:
    parsed = _parse_float(value, field="contamination_epsilon")
    if math.isclose(parsed, 0.0, abs_tol=1e-12):
        return "0"
    if math.isclose(parsed, 0.05, abs_tol=1e-12):
        return "0.05"
    return f"{parsed:g}"


def _mean_metric(rows: list[dict[str, Any]], key: str) -> float:
    return _mean([float(row[key]) for row in rows])


def _compact_rows(breakdown: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in breakdown:
        by_pair[(str(row["dataset"]), str(row["baseline"]))].append(row)

    for dataset_name, _ in EXPECTED_DATASETS.values():
        for baseline_name, _, memory_policy in EXPECTED_BASELINES.values():
            rows = by_pair.get((dataset_name, baseline_name), [])
            if len(rows) != len(EXPECTED_STREAM_TYPES) * len(EXPECTED_EPSILONS):
                raise StreamEpsilonSummaryError(
                    f"Cannot build compact stream/epsilon row for {dataset_name}|{baseline_name}"
                )
            iid_rows = [row for row in rows if row["stream_type"] == "iid"]
            bursty_rows = [row for row in rows if row["stream_type"] == "bursty"]
            eps_zero_rows = [row for row in rows if row["epsilon"] == "0"]
            eps_high_rows = [row for row in rows if row["epsilon"] == "0.05"]
            compact.append(
                {
                    "dataset": dataset_name,
                    "baseline": baseline_name,
                    "memory_policy": memory_policy,
                    "calibration": "none",
                    "row_count": sum(int(row["row_count"]) for row in rows),
                    "mean_image_auroc": _mean_metric(rows, "mean_image_auroc"),
                    "delta_bursty_iid_auroc": _mean_metric(
                        bursty_rows, "mean_image_auroc"
                    )
                    - _mean_metric(iid_rows, "mean_image_auroc"),
                    "delta_eps_0p05_0_auroc": _mean_metric(
                        eps_high_rows, "mean_image_auroc"
                    )
                    - _mean_metric(eps_zero_rows, "mean_image_auroc"),
                    "delta_eps_0p05_0_ece": _mean_metric(eps_high_rows, "mean_ece")
                    - _mean_metric(eps_zero_rows, "mean_ece"),
                    "mean_latency_ms": _mean_metric(rows, "mean_latency_ms"),
                }
            )
    return compact


def build_compact_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return _compact_rows(list(summary["breakdown"]))


def _seed_from_run_dir(row: dict[str, str]) -> str:
    run_dir = row.get("run_dir", "")
    marker = "_seed_"
    if marker not in run_dir:
        return ""
    return run_dir.rsplit(marker, 1)[-1].split("/", 1)[0]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise StreamEpsilonSummaryError(f"Missing category summary: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise StreamEpsilonSummaryError(f"Category summary must contain an object: {path}")
    return payload


def _validate_category_summary(summary: dict[str, Any], *, path: Path) -> None:
    if summary.get("status") != "category_shards_complete":
        raise StreamEpsilonSummaryError(f"Category summary is not complete: {path}")
    if summary.get("paper_allowed") is not False:
        raise StreamEpsilonSummaryError(f"paper_allowed must be false: {path}")
    if summary.get("claim_allowed") is not False:
        raise StreamEpsilonSummaryError(f"claim_allowed must be false: {path}")
    if summary.get("review_status") != "review_pending":
        raise StreamEpsilonSummaryError(f"review_status must be review_pending: {path}")


def _read_metric_rows(metrics_path: Path) -> list[dict[str, str]]:
    if not metrics_path.exists():
        raise StreamEpsilonSummaryError(f"Missing metrics CSV: {metrics_path}")
    with metrics_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED_METRIC_COLUMNS - set(reader.fieldnames or []))
        if missing:
            raise StreamEpsilonSummaryError(
                f"Missing required metric columns in {metrics_path}: {missing}"
            )
        rows = [dict(row) for row in reader]
    if not rows:
        raise StreamEpsilonSummaryError(f"No metric rows in {metrics_path}")
    return rows


def _summary_path(input_root: Path, dataset_slug: str, baseline_slug: str) -> Path:
    _, memory_slug, _ = EXPECTED_BASELINES[baseline_slug]
    return input_root / dataset_slug / baseline_slug / memory_slug / "none" / "category_summary.json"


def _collect_metric_rows(input_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dataset_slug, (dataset_name, expected_categories) in EXPECTED_DATASETS.items():
        for baseline_slug, (baseline_name, _, memory_policy) in EXPECTED_BASELINES.items():
            summary_path = _summary_path(input_root, dataset_slug, baseline_slug)
            summary = _load_json(summary_path)
            _validate_category_summary(summary, path=summary_path)
            if summary.get("dataset") != dataset_name:
                raise StreamEpsilonSummaryError(f"Unexpected dataset in {summary_path}")
            if summary.get("baseline") != baseline_name:
                raise StreamEpsilonSummaryError(f"Unexpected baseline in {summary_path}")
            if summary.get("memory_policy") != memory_policy:
                raise StreamEpsilonSummaryError(f"Unexpected memory policy in {summary_path}")
            if summary.get("calibration") != "none":
                raise StreamEpsilonSummaryError(f"Expected calibration=none in {summary_path}")
            if int(summary.get("complete_category_count", 0)) != expected_categories:
                raise StreamEpsilonSummaryError(f"Incomplete categories in {summary_path}")

            categories = summary.get("categories", [])
            if len(categories) != expected_categories:
                raise StreamEpsilonSummaryError(f"Unexpected category count in {summary_path}")
            for category in categories:
                if not category.get("complete"):
                    raise StreamEpsilonSummaryError(
                        f"Category is not complete in {summary_path}: {category.get('category')}"
                    )
                metrics_path = Path(str(category.get("metrics_csv", "")))
                for row in _read_metric_rows(metrics_path):
                    row = dict(row)
                    row["_source_metrics_csv"] = str(metrics_path)
                    rows.append(row)
    return rows


def _validate_metric_row(row: dict[str, str]) -> None:
    if row.get("status") != "measured_paper_candidate":
        raise StreamEpsilonSummaryError(
            f"Unexpected metric status in {row.get('_source_metrics_csv')}: {row.get('status')}"
        )
    if row.get("stream_type") not in EXPECTED_STREAM_TYPES:
        raise StreamEpsilonSummaryError(f"Unexpected stream type: {row.get('stream_type')}")
    if _epsilon_key(row.get("contamination_epsilon")) not in EXPECTED_EPSILONS:
        raise StreamEpsilonSummaryError(
            f"Unexpected epsilon: {row.get('contamination_epsilon')}"
        )
    for column in METRIC_COLUMNS:
        _parse_float(row.get(column), field=column)


def summarize_stream_epsilon(input_root: Path = DEFAULT_INPUT_ROOT) -> dict[str, Any]:
    metric_rows = _collect_metric_rows(input_root)
    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in metric_rows:
        _validate_metric_row(row)
        key = (
            row["dataset"],
            row["baseline"],
            row["stream_type"],
            _epsilon_key(row["contamination_epsilon"]),
        )
        groups[key].append(row)

    output_rows: list[dict[str, Any]] = []
    missing_groups: list[str] = []
    for dataset_name, expected_categories in EXPECTED_DATASETS.values():
        for baseline_name, _, memory_policy in EXPECTED_BASELINES.values():
            for stream_type in sorted(EXPECTED_STREAM_TYPES):
                for epsilon in sorted(EXPECTED_EPSILONS, key=float):
                    key = (dataset_name, baseline_name, stream_type, epsilon)
                    rows = groups.get(key, [])
                    if not rows:
                        missing_groups.append("|".join(key))
                        continue
                    categories = sorted({row["category"] for row in rows})
                    seeds = sorted({seed for row in rows if (seed := _seed_from_run_dir(row))})
                    expected_rows = expected_categories * 3
                    if len(rows) != expected_rows:
                        raise StreamEpsilonSummaryError(
                            f"Unexpected row count for {key}: {len(rows)} != {expected_rows}"
                        )
                    if len(categories) != expected_categories:
                        raise StreamEpsilonSummaryError(
                            f"Unexpected category count for {key}: {len(categories)}"
                        )
                    if len(seeds) != 3:
                        raise StreamEpsilonSummaryError(
                            f"Unexpected seed count for {key}: {len(seeds)}"
                        )
                    metric_means = {
                        f"mean_{column}": _mean(
                            [_parse_float(row[column], field=column) for row in rows]
                        )
                        for column in METRIC_COLUMNS
                    }
                    output_rows.append(
                        {
                            "dataset": dataset_name,
                            "baseline": baseline_name,
                            "memory_policy": memory_policy,
                            "calibration": "none",
                            "stream_type": stream_type,
                            "epsilon": epsilon,
                            "row_count": len(rows),
                            "category_count": len(categories),
                            "seed_count": len(seeds),
                            "paper_allowed": False,
                            "claim_allowed": False,
                            "review_status": "review_pending",
                            **metric_means,
                        }
                    )

    if missing_groups:
        raise StreamEpsilonSummaryError(f"Missing stream/epsilon groups: {missing_groups}")

    return {
        "status": "paper_candidate_stream_epsilon_breakdown_complete",
        "run_tier": "paper_candidate",
        "candidate_scope": "stream_epsilon_breakdown",
        "calibration": "none",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "dataset_count": len(EXPECTED_DATASETS),
        "baseline_count_per_dataset": len(EXPECTED_BASELINES),
        "group_row_count": len(output_rows),
        "expected_group_row_count": (
            len(EXPECTED_DATASETS)
            * len(EXPECTED_BASELINES)
            * len(EXPECTED_STREAM_TYPES)
            * len(EXPECTED_EPSILONS)
        ),
        "stream_types": sorted(EXPECTED_STREAM_TYPES),
        "epsilons": sorted(EXPECTED_EPSILONS, key=float),
        "breakdown": output_rows,
        "compact_breakdown": _compact_rows(output_rows),
        "notes": (
            "No-inference breakdown over completed paper-candidate category "
            "shards. This does not promote paper_allowed or claim_allowed."
        ),
    }


def write_csv(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in summary["breakdown"]:
            writer.writerow({column: _format_value(row.get(column, "")) for column in OUTPUT_COLUMNS})


def write_json(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")


def write_tex(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = COMPACT_TEX_COLUMNS
    compact_rows = summary.get("compact_breakdown") or _compact_rows(summary["breakdown"])
    lines = [
        "% Auto-generated compact stream/epsilon summary for the paper table.",
        "% Full 32-row breakdown remains in the paired CSV/JSON artifacts.",
        "\\begin{tabular}{llrrrrr}",
        "\\toprule",
        " & ".join(label for _, label in columns) + r" \\",
        "\\midrule",
    ]
    for row in compact_rows:
        lines.append(
            " & ".join(_compact_tex_value(row, key) for key, _ in columns) + r" \\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
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
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize_stream_epsilon(input_root=args.input_root)
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
        f"{summary['status']} groups={summary['group_row_count']} "
        "paper_allowed=false claim_allowed=false review_status=review_pending"
    )


if __name__ == "__main__":
    main()
