#!/usr/bin/env python3
"""Render paper-candidate analysis tables and figures without inference."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from experiments.summarize_paper_candidate_all_datasets import (
    CombinedComparisonError,
    _rank_dataset,
    _tex_escape,
    summarize_all_datasets,
)

DEFAULT_INPUT_CSV = Path(
    "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv"
)
DEFAULT_INPUT_JSON = Path(
    "results/latest/paper_candidate/baseline_comparison_all_datasets_none.json"
)
DEFAULT_RANKING_JSON = Path(
    "results/latest/paper_candidate/baseline_ranking_summary.json"
)
DEFAULT_RANKING_TEX = Path("results/latest/tables/paper_candidate_ranking_summary.tex")
DEFAULT_FIGURE_PNG = Path(
    "results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png"
)
DEFAULT_FIGURE_PDF = Path(
    "results/latest/figures/paper_candidate_accuracy_latency_tradeoff.pdf"
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CombinedComparisonError(f"Missing combined comparison JSON: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise CombinedComparisonError(f"JSON file must contain an object: {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise CombinedComparisonError(f"Missing combined comparison CSV: {path}")
    with path.open(newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if not rows:
        raise CombinedComparisonError(f"No rows in combined comparison CSV: {path}")
    return rows


def _float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CombinedComparisonError(f"Invalid numeric value for {key}: {value!r}") from exc


def _validate_combined_summary(summary: dict[str, Any], *, path: Path) -> None:
    if summary.get("status") != "paper_candidate_combined_baseline_comparison_complete":
        raise CombinedComparisonError(f"Combined summary is not complete: {path}")
    if summary.get("paper_allowed") is not False:
        raise CombinedComparisonError(f"paper_allowed must be false: {path}")
    if summary.get("claim_allowed") is not False:
        raise CombinedComparisonError(f"claim_allowed must be false: {path}")
    if summary.get("review_status") != "review_pending":
        raise CombinedComparisonError(f"review_status must be review_pending: {path}")
    if int(summary.get("dataset_count", 0)) < 1:
        raise CombinedComparisonError(f"dataset_count must be positive: {path}")
    if int(summary.get("baseline_row_count", 0)) < 1:
        raise CombinedComparisonError(f"baseline_row_count must be positive: {path}")


def build_ranking_summary(
    *,
    combined_csv: Path = DEFAULT_INPUT_CSV,
    combined_json: Path = DEFAULT_INPUT_JSON,
) -> dict[str, Any]:
    combined = _read_json(combined_json)
    _validate_combined_summary(combined, path=combined_json)

    rows = summarize_all_datasets([combined_csv])["baselines"]
    if len(rows) != int(combined.get("baseline_row_count", 0)):
        raise CombinedComparisonError("CSV row count does not match combined JSON")

    rankings: dict[str, dict[str, dict[str, Any]]] = {}
    for dataset in sorted({str(row["dataset"]) for row in rows}):
        rankings[dataset] = _rank_dataset(
            [row for row in rows if row["dataset"] == dataset]
        )

    return {
        "status": "paper_candidate_ranking_summary_complete",
        "run_tier": "paper_candidate",
        "candidate_scope": "ranking_summary",
        "source_csv": str(combined_csv),
        "source_json": str(combined_json),
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "dataset_count": combined["dataset_count"],
        "baseline_row_count": combined["baseline_row_count"],
        "rankings": rankings,
        "accuracy_latency_tradeoff_notes": combined.get(
            "accuracy_latency_tradeoff_notes", []
        ),
        "notes": "Ranking summary for the compact paper-evaluation analysis.",
    }


def write_ranking_json(summary: dict[str, Any], path: Path = DEFAULT_RANKING_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return path


def write_ranking_tex(summary: dict[str, Any], path: Path = DEFAULT_RANKING_TEX) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "% Auto-generated ranking summary from the compact evaluation slice.",
        "\\begin{tabular}{lllll}",
        "\\toprule",
        "Dataset & AUROC $\\uparrow$ & AUPR $\\uparrow$ & ECE $\\downarrow$ & Latency $\\downarrow$ \\\\",
        "\\midrule",
    ]
    for dataset, rankings in summary["rankings"].items():
        lines.append(
            " & ".join(
                [
                    _tex_escape(dataset),
                    _tex_escape(rankings["best_auroc"]["baseline"]),
                    _tex_escape(rankings["best_aupr"]["baseline"]),
                    _tex_escape(rankings["lowest_ece"]["baseline"]),
                    _tex_escape(rankings["lowest_latency"]["baseline"]),
                ]
            )
            + r" \\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    for note in summary["accuracy_latency_tradeoff_notes"]:
        lines.append("% " + _tex_escape(note))
    path.write_text("\n".join(lines) + "\n")
    return path


def write_tradeoff_figure(
    *,
    combined_csv: Path = DEFAULT_INPUT_CSV,
    output_png: Path = DEFAULT_FIGURE_PNG,
    output_pdf: Path = DEFAULT_FIGURE_PDF,
) -> tuple[Path, Path | None]:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/ziad_matplotlib")
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = _read_csv_rows(combined_csv)
    datasets = sorted({row["dataset"] for row in rows})
    baselines = sorted({row["baseline"] for row in rows})
    markers = ["o", "s", "^", "D", "P", "X"]
    colors = {
        "PatchCore": "#1f77b4",
        "WinCLIP": "#ff7f0e",
        "AnomalyCLIP": "#2ca02c",
        "RareCLIP": "#d62728",
    }

    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(6.6, 3.8), constrained_layout=True)
    for dataset_index, dataset in enumerate(datasets):
        marker = markers[dataset_index % len(markers)]
        for row in [item for item in rows if item["dataset"] == dataset]:
            baseline = row["baseline"]
            latency = _float(row, "mean_latency_ms")
            auroc = _float(row, "mean_image_auroc")
            ax.scatter(
                latency,
                auroc,
                marker=marker,
                s=70,
                color=colors.get(baseline, "#555555"),
                edgecolor="black",
                linewidth=0.5,
            )

    ax.set_xlabel("Mean latency (ms)")
    ax.set_ylabel("Mean image AUROC")
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    ax.margins(x=0.08, y=0.08)

    baseline_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label=baseline,
            markerfacecolor=colors.get(baseline, "#555555"),
            markeredgecolor="black",
            markersize=6,
        )
        for baseline in baselines
    ]
    dataset_handles = [
        Line2D(
            [0],
            [0],
            marker=markers[index % len(markers)],
            color="#374151",
            label=dataset,
            linestyle="None",
            markersize=6,
        )
        for index, dataset in enumerate(datasets)
    ]
    first_legend = ax.legend(
        handles=baseline_handles,
        fontsize=7,
        loc="lower right",
        title="Baseline",
        title_fontsize=7,
        frameon=True,
    )
    ax.add_artist(first_legend)
    ax.legend(
        handles=dataset_handles,
        fontsize=7,
        loc="upper left",
        title="Dataset",
        title_fontsize=7,
        frameon=True,
    )

    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    pdf_path: Path | None = None
    try:
        fig.savefig(output_pdf)
        pdf_path = output_pdf
    finally:
        plt.close(fig)
    return output_png, pdf_path


def write_outputs(
    *,
    combined_csv: Path = DEFAULT_INPUT_CSV,
    combined_json: Path = DEFAULT_INPUT_JSON,
    ranking_json: Path = DEFAULT_RANKING_JSON,
    ranking_tex: Path = DEFAULT_RANKING_TEX,
    figure_png: Path = DEFAULT_FIGURE_PNG,
    figure_pdf: Path = DEFAULT_FIGURE_PDF,
) -> dict[str, Any]:
    summary = build_ranking_summary(combined_csv=combined_csv, combined_json=combined_json)
    ranking_json_path = write_ranking_json(summary, ranking_json)
    ranking_tex_path = write_ranking_tex(summary, ranking_tex)
    figure_png_path, figure_pdf_path = write_tradeoff_figure(
        combined_csv=combined_csv,
        output_png=figure_png,
        output_pdf=figure_pdf,
    )
    return {
        "ranking_summary": summary,
        "ranking_json": ranking_json_path,
        "ranking_tex": ranking_tex_path,
        "figure_png": figure_png_path,
        "figure_pdf": figure_pdf_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--combined-json", type=Path, default=DEFAULT_INPUT_JSON)
    parser.add_argument("--ranking-json", type=Path, default=DEFAULT_RANKING_JSON)
    parser.add_argument("--ranking-tex", type=Path, default=DEFAULT_RANKING_TEX)
    parser.add_argument("--figure-png", type=Path, default=DEFAULT_FIGURE_PNG)
    parser.add_argument("--figure-pdf", type=Path, default=DEFAULT_FIGURE_PDF)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = write_outputs(
        combined_csv=args.combined_csv,
        combined_json=args.combined_json,
        ranking_json=args.ranking_json,
        ranking_tex=args.ranking_tex,
        figure_png=args.figure_png,
        figure_pdf=args.figure_pdf,
    )
    print(outputs["figure_png"])
    if outputs["figure_pdf"] is not None:
        print(outputs["figure_pdf"])
    print(outputs["ranking_json"])
    print(outputs["ranking_tex"])
    summary = outputs["ranking_summary"]
    print(
        "status="
        f"{summary['status']} datasets={summary['dataset_count']} "
        f"rows={summary['baseline_row_count']} paper_allowed=false claim_allowed=false"
    )


if __name__ == "__main__":
    main()
