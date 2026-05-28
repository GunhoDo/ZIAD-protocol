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
DEFAULT_INPUT_CONTRACT = Path("results/latest/tables/paper_input_contract.json")
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


def _csv_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open(newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


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


def _known_table_inputs() -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = [
        {
            "name": "p0_smoke_summary",
            "kind": "summary_table",
            "tex": "results/latest/tables/p0_smoke_summary.tex",
            "source_csv": "results/latest/tables/p0_smoke_summary.csv",
            "manifest": "results/latest/tables/p0_smoke_summary_manifest.json",
            "included_in_paper_tex": True,
            "paper_label": "tab:p0-smoke-summary",
            "interpretation": "compact smoke evidence summary; not a reviewed P0 result",
        },
        {
            "name": "mvtec_category_quick_sweep",
            "kind": "smoke_table",
            "tex": "results/latest/tables/smoke_evidence_summary.tex",
            "source_csv": str(DEFAULT_METRICS),
            "manifest": str(DEFAULT_MANIFEST),
            "included_in_paper_tex": True,
            "paper_label": DEFAULT_LABEL,
            "interpretation": "MVTec quick-sweep smoke evidence; not a reviewed P0 result",
        },
    ]
    pretty = {
        "winclip": "WinCLIP",
        "anomalyclip": "AnomalyCLIP",
        "rareclip": "RareCLIP",
        "patchcore": "PatchCore",
    }
    for dataset in ["mvtec", "visa"]:
        dataset_title = "MVTec AD" if dataset == "mvtec" else "VisA"
        for baseline in ["winclip", "anomalyclip", "rareclip", "patchcore"]:
            stem = f"{dataset}_full_category_stream_matrix_{baseline}_temperature"
            inputs.append(
                {
                    "name": f"{dataset}_{baseline}_temperature_smoke",
                    "kind": "calibration_axis_smoke_table",
                    "tex": f"results/latest/tables/{dataset}_{baseline}_temperature_smoke.tex",
                    "source_csv": f"results/latest/{stem}/metrics_{stem}.csv",
                    "manifest": f"results/latest/{stem}/manifest_{stem}.json",
                    "included_in_paper_tex": False,
                    "paper_label": f"tab:{dataset}-{baseline}-temperature-smoke",
                    "interpretation": (
                        f"{dataset_title} {pretty[baseline]} stream/epsilon/calibration "
                        "smoke evidence; not a reviewed P0 result"
                    ),
                }
            )
    inputs.extend(
        [
            {
                "name": "paper_candidate_combined_baseline_comparison",
                "kind": "paper_candidate_table",
                "tex": "results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex",
                "source_csv": "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv",
                "manifest": "results/latest/paper_candidate/baseline_comparison_all_datasets_none.json",
                "included_in_paper_tex": False,
                "paper_label": "tab:paper-candidate-baseline-comparison",
                "interpretation": (
                    "MVTec AD and VisA paper-candidate baseline comparison; "
                    "review-pending and not a promoted paper result"
                ),
            },
            {
                "name": "paper_candidate_ranking_summary",
                "kind": "paper_candidate_table",
                "tex": "results/latest/tables/paper_candidate_ranking_summary.tex",
                "source_csv": "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv",
                "manifest": "results/latest/paper_candidate/baseline_ranking_summary.json",
                "included_in_paper_tex": False,
                "paper_label": "tab:paper-candidate-ranking-summary",
                "interpretation": (
                    "Ranking summary for review-pending paper-candidate analysis; "
                    "not a promoted paper result"
                ),
            },
            {
                "name": "paper_candidate_accuracy_latency_tradeoff",
                "kind": "paper_candidate_figure",
                "tex": "results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png",
                "source_csv": "results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv",
                "manifest": "results/latest/paper_candidate/baseline_ranking_summary.json",
                "included_in_paper_tex": False,
                "paper_label": "fig:paper-candidate-accuracy-latency",
                "interpretation": (
                    "Accuracy-latency trade-off figure for review-pending "
                    "paper-candidate analysis; not a promoted paper result"
                ),
            },
        ]
    )
    return inputs


def write_paper_input_contract(
    output_path: Path = DEFAULT_INPUT_CONTRACT,
    *,
    table_inputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write the current paper table/figure input contract.

    The contract is metadata only. It records generated table inputs and keeps
    every current artifact paper-ineligible until full reviewed P0 results are
    explicitly promoted.
    """
    inputs = table_inputs or _known_table_inputs()
    normalized: list[dict[str, Any]] = []
    any_missing = False
    any_paper_allowed = False
    for entry in inputs:
        manifest_path = Path(entry["manifest"])
        source_csv = Path(entry["source_csv"])
        tex_path = Path(entry["tex"])
        manifest = _read_json(manifest_path)
        paper_allowed = bool(manifest.get("paper_allowed"))
        any_paper_allowed = any_paper_allowed or paper_allowed
        missing = [
            str(path)
            for path in [tex_path, source_csv, manifest_path]
            if not path.exists()
        ]
        any_missing = any_missing or bool(missing)
        normalized.append(
            {
                **entry,
                "exists": not missing,
                "missing": missing,
                "row_count": _csv_row_count(source_csv),
                "source_manifest_status": manifest.get("status", "unknown"),
                "source_paper_allowed": paper_allowed,
                "eligible_for_claims": False,
            }
        )

    table_entries = [entry for entry in normalized if "figure" not in entry["kind"]]
    figure_entries = [entry for entry in normalized if "figure" in entry["kind"]]
    contract = {
        "status": (
            "paper_input_contract_incomplete"
            if any_missing
            else "paper_input_contract_ready_smoke_only"
        ),
        "paper_allowed": False,
        "claim_allowed": False,
        "table_count": len(table_entries),
        "figure_count": len(figure_entries),
        "included_table_count": sum(
            1 for entry in table_entries if entry["included_in_paper_tex"]
        ),
        "missing_input_count": sum(len(entry["missing"]) for entry in normalized),
        "source_paper_allowed_count": sum(
            1 for entry in normalized if entry["source_paper_allowed"]
        ),
        "tables": table_entries,
        "figures": figure_entries,
        "notes": (
            "This contract enumerates current generated paper inputs. They are "
            "smoke evidence only; do not treat them as reviewed paper results or "
            "promote paper_allowed without a separate review step."
        ),
    }
    if any_paper_allowed:
        contract["notes"] += " One or more source manifests is paper_allowed=true."

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
    return contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-csv", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--caption", default=DEFAULT_CAPTION)
    parser.add_argument("--label", default=DEFAULT_LABEL)
    parser.add_argument(
        "--write-input-contract",
        action="store_true",
        help="Write the current paper table/figure input contract instead of rendering one table.",
    )
    parser.add_argument("--input-contract-output", type=Path, default=DEFAULT_INPUT_CONTRACT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write_input_contract:
        write_paper_input_contract(args.input_contract_output)
        print(args.input_contract_output)
        return
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
