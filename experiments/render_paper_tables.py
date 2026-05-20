#!/usr/bin/env python3
"""Render paper-facing tables from checked result artifacts.

The renderer is deliberately conservative. It can expose measured smoke
evidence in the manuscript build, but it keeps non-final runs clearly marked as
paper-ineligible and never promotes outputs to paper results.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_METRICS = Path(
    "results/latest/category_quick_sweep/metrics_mvtec_category_quick_sweep.csv"
)
DEFAULT_MANIFEST = Path(
    "results/latest/category_quick_sweep/manifest_mvtec_category_quick_sweep.json"
)
DEFAULT_OUTPUT = Path("results/latest/tables/smoke_evidence_summary.tex")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing metrics CSV: {path}")
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _latex_escape(value: Any) -> str:
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
    return "".join(replacements.get(character, character) for character in text)


def _format_cell(row: dict[str, str], key: str) -> str:
    value = row.get(key, "NA")
    if value == "":
        value = "NA"
    return _latex_escape(value)


def _sort_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("category", ""),
        row.get("baseline", ""),
        row.get("stream_type", ""),
        row.get("contamination_epsilon", ""),
    )


def render_smoke_evidence_table(
    metrics_csv: Path = DEFAULT_METRICS,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
) -> str:
    rows = _read_csv(metrics_csv)
    if not rows:
        raise SystemExit(f"No metric rows found: {metrics_csv}")

    manifest = _read_json(manifest_path)
    paper_allowed = bool(manifest.get("paper_allowed"))
    status = str(manifest.get("status", "unknown"))
    if paper_allowed:
        note = "final paper-allowed result table"
        caption_suffix = "final result"
    else:
        note = "smoke evidence only; paper_allowed=false"
        caption_suffix = "non-final, paper-ineligible smoke evidence"

    lines = [
        f"% Auto-generated from {metrics_csv}.",
        f"% Manifest: {manifest_path}; status={status}; {note}.",
        "\\begin{table}[t]",
        f"\\caption{{MVTec AD category quick-sweep metrics ({caption_suffix}).}}",
        "\\label{tab:mvtec-category-quick-sweep}",
        "\\centering",
        "\\begin{tabular}{llccccc}",
        "\\hline",
        "Category & Baseline & AUROC & AUPR & ECE & Latency & CRD-lite \\\\",
        "\\hline",
    ]
    for row in sorted(rows, key=_sort_key):
        lines.append(
            " & ".join(
                [
                    _format_cell(row, "category"),
                    _format_cell(row, "baseline"),
                    _format_cell(row, "image_auroc"),
                    _format_cell(row, "aupr"),
                    _format_cell(row, "ece"),
                    _format_cell(row, "latency_ms"),
                    _format_cell(row, "crd_lite"),
                ]
            )
            + r" \\"
        )
    lines.extend(
        [
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )

    body = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body)
    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-csv", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render_smoke_evidence_table(args.metrics_csv, args.manifest, args.output)
    print(args.output)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:  # pragma: no cover - shell pipeline behavior
        sys.exit(1)
