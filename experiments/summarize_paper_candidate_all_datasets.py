#!/usr/bin/env python3
"""Combine paper-candidate baseline comparison tables across datasets."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_INPUT_CSVS = [
    Path("results/latest/paper_candidate/mvtec_ad/baseline_comparison_none.csv"),
    Path("results/latest/paper_candidate/visa/baseline_comparison_none.csv"),
]
DEFAULT_OUTPUT_CSV = Path(
    "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv"
)
DEFAULT_OUTPUT_JSON = Path(
    "results/latest/paper_candidate/baseline_comparison_all_datasets_none.json"
)
DEFAULT_OUTPUT_TEX = Path(
    "results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex"
)

OUTPUT_COLUMNS = [
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

RANKING_METRICS = {
    "best_auroc": ("mean_image_auroc", "max"),
    "best_aupr": ("mean_aupr", "max"),
    "lowest_ece": ("mean_ece", "min"),
    "lowest_latency": ("mean_latency_ms", "min"),
}


class CombinedComparisonError(ValueError):
    """Raised when combined paper-candidate comparison inputs are invalid."""


def _parse_bool(value: Any, *, field: str, path: Path) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized == "false":
        return False
    if normalized == "true":
        return True
    raise CombinedComparisonError(f"{field} must be boolean-like in {path}: {value!r}")


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


def _format_value(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, bool):
        return "False" if value is False else "True"
    return str(value)


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise CombinedComparisonError(f"Missing baseline comparison CSV: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in OUTPUT_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise CombinedComparisonError(f"Missing required columns in {path}: {missing}")
        rows = []
        for row in reader:
            normalized = {column: row.get(column, "") for column in OUTPUT_COLUMNS}
            normalized["paper_allowed"] = _parse_bool(
                normalized["paper_allowed"], field="paper_allowed", path=path
            )
            normalized["claim_allowed"] = _parse_bool(
                normalized["claim_allowed"], field="claim_allowed", path=path
            )
            if normalized["paper_allowed"] is not False:
                raise CombinedComparisonError(f"paper_allowed must be false in {path}")
            if normalized["claim_allowed"] is not False:
                raise CombinedComparisonError(f"claim_allowed must be false in {path}")
            if normalized["review_status"] != "review_pending":
                raise CombinedComparisonError(
                    f"review_status must be review_pending in {path}"
                )
            for integer_column in (
                "completed_categories",
                "expected_categories",
                "total_rows",
            ):
                normalized[integer_column] = int(normalized[integer_column])
            for metric_column in (
                "mean_image_auroc",
                "mean_aupr",
                "mean_ece",
                "mean_latency_ms",
                "mean_crd_lite",
            ):
                normalized[metric_column] = _parse_float(normalized[metric_column])
            rows.append(normalized)
    if not rows:
        raise CombinedComparisonError(f"No rows in baseline comparison CSV: {path}")
    return rows


def _rank_dataset(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rankings: dict[str, dict[str, Any]] = {}
    for ranking_name, (column, direction) in RANKING_METRICS.items():
        candidates = [row for row in rows if row.get(column) is not None]
        if not candidates:
            rankings[ranking_name] = {
                "metric": column,
                "baseline": None,
                "memory_policy": None,
                "value": None,
            }
            continue
        reverse = direction == "max"
        best = sorted(
            candidates,
            key=lambda row: (float(row[column]), str(row["baseline"])),
            reverse=reverse,
        )[0]
        rankings[ranking_name] = {
            "metric": column,
            "baseline": best["baseline"],
            "memory_policy": best["memory_policy"],
            "value": best[column],
        }
    return rankings


def _tradeoff_note(dataset: str, rankings: dict[str, dict[str, Any]]) -> str:
    auroc = rankings["best_auroc"]["baseline"]
    latency = rankings["lowest_latency"]["baseline"]
    if auroc is None or latency is None:
        return f"{dataset}: insufficient metric coverage for accuracy-latency trade-off."
    if auroc == latency:
        return f"{dataset}: {auroc} leads AUROC and latency in this compact evaluation slice."
    return (
        f"{dataset}: {auroc} leads AUROC, while {latency} has the lowest latency; "
        "this highlights an accuracy-latency trade-off in the compact evaluation slice."
    )


def summarize_all_datasets(input_csvs: list[Path] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in input_csvs or DEFAULT_INPUT_CSVS:
        rows.extend(_load_rows(path))

    datasets = sorted({str(row["dataset"]) for row in rows})
    if not datasets:
        raise CombinedComparisonError("No datasets found")
    if {row["calibration"] for row in rows} != {"none"}:
        raise CombinedComparisonError("Combined paper-candidate table expects calibration=none")

    rankings: dict[str, dict[str, dict[str, Any]]] = {}
    tradeoff_notes: list[str] = []
    for dataset in datasets:
        dataset_rows = [row for row in rows if row["dataset"] == dataset]
        dataset_rankings = _rank_dataset(dataset_rows)
        rankings[dataset] = dataset_rankings
        tradeoff_notes.append(_tradeoff_note(dataset, dataset_rankings))

    return {
        "status": "paper_candidate_combined_baseline_comparison_complete",
        "run_tier": "paper_candidate",
        "candidate_scope": "combined_baseline_comparison",
        "calibration": "none",
        "dataset_count": len(datasets),
        "datasets": datasets,
        "baseline_row_count": len(rows),
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "baselines": rows,
        "rankings": rankings,
        "accuracy_latency_tradeoff_notes": tradeoff_notes,
        "notes": (
            "Combined paper-candidate comparison only. All rows remain "
            "review_pending with paper_allowed=false and claim_allowed=false."
        ),
    }


def write_csv(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in summary["baselines"]:
            writer.writerow({column: _format_value(row.get(column)) for column in OUTPUT_COLUMNS})


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


def _tex_metric(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return "NA"
    if key == "mean_latency_ms":
        return f"{float(value):.1f}"
    return f"{float(value):.3f}"


def write_tex(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        ("dataset", "Dataset"),
        ("baseline", "Baseline"),
        ("completed_categories", "Cat."),
        ("total_rows", "Rows"),
        ("mean_image_auroc", "AUROC"),
        ("mean_aupr", "AUPR"),
        ("mean_ece", "ECE"),
        ("mean_latency_ms", "Lat. (ms)"),
        ("mean_crd_lite", "CRD-lite"),
    ]
    lines = [
        "% Auto-generated compact evaluation table.",
        "\\begin{tabular}{@{}l@{\\hspace{0.8em}}l@{\\hspace{0.7em}}c@{\\hspace{0.7em}}c@{\\hspace{0.7em}}rrrrr@{}}",
        "\\toprule",
        " & ".join(label for _, label in columns) + r" \\",
        "\\midrule",
    ]
    previous_dataset = None
    for row in summary["baselines"]:
        dataset = row.get("dataset")
        if previous_dataset is not None and dataset != previous_dataset:
            lines.append("\\addlinespace[0.18em]")
        previous_dataset = dataset
        values = []
        for key, _ in columns:
            value = row.get(key)
            if key == "completed_categories":
                value = f"{row.get('completed_categories')}/{row.get('expected_categories')}"
                values.append(_tex_escape(value))
            elif key.startswith("mean_"):
                values.append(_tex_metric(row, key))
            else:
                values.append(_tex_escape(value))
        lines.append(" & ".join(values) + r" \\")
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    for dataset, rankings in summary["rankings"].items():
        lines.append(
            "% "
            + _tex_escape(dataset)
            + " rankings: AUROC="
            + _tex_escape(rankings["best_auroc"]["baseline"])
            + ", AUPR="
            + _tex_escape(rankings["best_aupr"]["baseline"])
            + ", ECE="
            + _tex_escape(rankings["lowest_ece"]["baseline"])
            + ", latency="
            + _tex_escape(rankings["lowest_latency"]["baseline"])
        )
    for note in summary["accuracy_latency_tradeoff_notes"]:
        lines.append("% " + _tex_escape(note))
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
    parser.add_argument("--input-csv", action="append", type=Path, dest="input_csvs")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = summarize_all_datasets(args.input_csvs)
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
        f"{summary['status']} datasets={summary['dataset_count']} "
        f"rows={summary['baseline_row_count']} paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
