#!/usr/bin/env python3
"""Summarize paper-ineligible P0 smoke matrices into compact table inputs."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.render_paper_tables import _latex_escape

BASELINES = ["winclip", "anomalyclip", "rareclip", "patchcore"]
DATASETS = ["mvtec", "visa"]
DEFAULT_METRICS = [
    Path(
        f"results/latest/{dataset}_full_category_stream_matrix_{baseline}_temperature/"
        f"metrics_{dataset}_full_category_stream_matrix_{baseline}_temperature.csv"
    )
    for dataset in DATASETS
    for baseline in BASELINES
]
DEFAULT_OUTPUT = Path("results/latest/tables/p0_smoke_summary.csv")
DEFAULT_MANIFEST = Path("results/latest/tables/p0_smoke_summary_manifest.json")
DEFAULT_TEX = Path("results/latest/tables/p0_smoke_summary.tex")
SUMMARY_FIELDS = [
    "dataset",
    "baseline",
    "memory_policy",
    "calibration",
    "category_count",
    "run_count",
    "stream_type_count",
    "epsilon_count",
    "mean_image_auroc",
    "mean_aupr",
    "mean_ece",
    "mean_latency_ms",
    "mean_crd_lite",
    "status",
    "paper_allowed",
]
NUMERIC_FIELDS = [
    "image_auroc",
    "aupr",
    "ece",
    "latency_ms",
    "crd_lite",
]


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing metrics CSV: {path}")
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"No metric rows found: {path}")
    return rows


def _mean(values: list[float]) -> str:
    return f"{sum(values) / len(values):.6f}"


def summarize_metrics(metrics_paths: list[Path]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for path in metrics_paths:
        for row in _read_rows(path):
            status = row.get("status", "")
            if status != "measured_smoke":
                raise SystemExit(f"Unexpected metric status {status!r} in {path}")
            key = (
                row.get("dataset", ""),
                row.get("baseline", ""),
                row.get("memory_policy", "default/SCS") or "default/SCS",
                row.get("calibration", "none") or "none",
            )
            if not all(key):
                raise SystemExit(
                    f"Missing dataset/baseline/memory_policy/calibration in {path}"
                )
            groups[key].append(row)

    summaries: list[dict[str, str]] = []
    for key in sorted(groups):
        dataset, baseline, memory_policy, calibration = key
        rows = groups[key]
        numeric: dict[str, list[float]] = {field: [] for field in NUMERIC_FIELDS}
        for row in rows:
            for field in NUMERIC_FIELDS:
                try:
                    numeric[field].append(float(row[field]))
                except (KeyError, ValueError) as error:
                    raise SystemExit(
                        f"Invalid numeric field {field!r} for {dataset}/{baseline}/{calibration}"
                    ) from error
        summaries.append(
            {
                "dataset": dataset,
                "baseline": baseline,
                "memory_policy": memory_policy,
                "calibration": calibration,
                "category_count": str(len({row["category"] for row in rows})),
                "run_count": str(len(rows)),
                "stream_type_count": str(len({row["stream_type"] for row in rows})),
                "epsilon_count": str(
                    len({row["contamination_epsilon"] for row in rows})
                ),
                "mean_image_auroc": _mean(numeric["image_auroc"]),
                "mean_aupr": _mean(numeric["aupr"]),
                "mean_ece": _mean(numeric["ece"]),
                "mean_latency_ms": _mean(numeric["latency_ms"]),
                "mean_crd_lite": _mean(numeric["crd_lite"]),
                "status": "measured_smoke_summary",
                "paper_allowed": "false",
            }
        )
    return summaries


def write_summary_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(
    path: Path,
    *,
    metrics_paths: list[Path],
    summary_csv: Path,
    table_tex: Path,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    manifest = {
        "status": "p0_smoke_summary_complete",
        "paper_allowed": False,
        "source_metrics": [str(path) for path in metrics_paths],
        "summary_csv": str(summary_csv),
        "table_tex": str(table_tex),
        "row_count": len(rows),
        "datasets": sorted({row["dataset"] for row in rows}),
        "baselines": sorted({row["baseline"] for row in rows}),
        "memory_policies": sorted({row["memory_policy"] for row in rows}),
        "calibration": sorted({row["calibration"] for row in rows}),
        "notes": (
            "Compact summary of measured smoke matrices only; paper-ineligible "
            "and not a reviewed full-P0 result."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def render_summary_table(
    rows: list[dict[str, str]],
    output_path: Path,
    *,
    summary_csv: Path,
    manifest_path: Path,
) -> str:
    lines = [
        f"% Auto-generated from {summary_csv}.",
        f"% Manifest: {manifest_path}; smoke evidence only; paper_allowed=false.",
        "\\begin{table}[t]",
        "\\caption{P0 smoke matrix summary (non-final, paper-ineligible smoke evidence).}",
        "\\label{tab:p0-smoke-summary}",
        "\\centering",
        "\\begin{tabular}{llllrrrrrr}",
        "\\hline",
        (
            "Dataset & Baseline & Memory & Calibration & Categories & Runs & AUROC & "
            "AUPR & ECE & Latency \\\\"
        ),
        "\\hline",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                [
                    _latex_escape(row["dataset"]),
                    _latex_escape(row["baseline"]),
                    _latex_escape(row["memory_policy"]),
                    _latex_escape(row["calibration"]),
                    row["category_count"],
                    row["run_count"],
                    row["mean_image_auroc"],
                    row["mean_aupr"],
                    row["mean_ece"],
                    row["mean_latency_ms"],
                ]
            )
            + r" \\"
        )
    lines.extend(["\\hline", "\\end{tabular}", "\\end{table}", ""])
    body = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body)
    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metrics-csv",
        type=Path,
        action="append",
        dest="metrics_csv",
        help="Metrics CSV to include. Repeatable; defaults to all current P0 smoke temperature aggregates.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tex-output", type=Path, default=DEFAULT_TEX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics_paths = args.metrics_csv or DEFAULT_METRICS
    rows = summarize_metrics(metrics_paths)
    write_summary_csv(args.output, rows)
    write_manifest(
        args.manifest,
        metrics_paths=metrics_paths,
        summary_csv=args.output,
        table_tex=args.tex_output,
        rows=rows,
    )
    render_summary_table(
        rows,
        args.tex_output,
        summary_csv=args.output,
        manifest_path=args.manifest,
    )
    print(args.output)
    print(args.manifest)
    print(args.tex_output)


if __name__ == "__main__":
    main()
