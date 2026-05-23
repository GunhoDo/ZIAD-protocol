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
DEFAULT_CAPTION = "MVTec AD category quick-sweep metrics"
DEFAULT_LABEL = "tab:mvtec-category-quick-sweep"
DEFAULT_TABLE_COLUMNS = [
    ("category", "Category", "l"),
    ("baseline", "Baseline", "l"),
    ("stream_type", "Stream", "l"),
    ("contamination_epsilon", r"$\epsilon$", "c"),
    ("calibration", "Calibration", "l"),
    ("image_auroc", "AUROC", "c"),
    ("aupr", "AUPR", "c"),
    ("ece", "ECE", "c"),
    ("latency_ms", "Latency", "c"),
    ("crd_lite", "CRD-lite", "c"),
]


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


def _sort_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("category", ""),
        row.get("baseline", ""),
        row.get("stream_type", ""),
        row.get("contamination_epsilon", ""),
        row.get("calibration", ""),
    )


def _visible_columns(rows: list[dict[str, str]]) -> list[tuple[str, str, str]]:
    columns: list[tuple[str, str, str]] = []
    for key, label, alignment in DEFAULT_TABLE_COLUMNS:
        if key in {"stream_type", "contamination_epsilon", "calibration"}:
            if not any(row.get(key, "") not in {"", "NA"} for row in rows):
                continue
        columns.append((key, label, alignment))
    return columns


def render_smoke_evidence_table(
    metrics_csv: Path = DEFAULT_METRICS,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    *,
    caption: str = DEFAULT_CAPTION,
    label: str = DEFAULT_LABEL,
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
    columns = _visible_columns(rows)

    lines = [
        f"% Auto-generated from {metrics_csv}.",
        f"% Manifest: {manifest_path}; status={status}; {note}.",
        "\\begin{table}[t]",
        f"\\caption{{{_latex_escape(caption)} ({caption_suffix}).}}",
        f"\\label{{{_latex_escape(label)}}}",
        "\\centering",
        "\\begin{tabular}{" + "".join(column[2] for column in columns) + "}",
        "\\hline",
        " & ".join(column[1] for column in columns) + r" \\",
        "\\hline",
    ]
    for row in sorted(rows, key=_sort_key):
        lines.append(
            " & ".join(_format_cell(row, column[0]) for column in columns)
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
    parser.add_argument("--caption", default=DEFAULT_CAPTION)
    parser.add_argument("--label", default=DEFAULT_LABEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render_smoke_evidence_table(
        args.metrics_csv,
        args.manifest,
        args.output,
        caption=args.caption,
        label=args.label,
    )
    print(args.output)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:  # pragma: no cover - shell pipeline behavior
        sys.exit(1)
