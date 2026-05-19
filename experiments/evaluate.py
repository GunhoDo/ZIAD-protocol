#!/usr/bin/env python3
"""Maintain results/latest placeholder metrics, table, and manifest.

This is a safety-first placeholder evaluator: until real score CSVs exist, it
keeps all result fields as TODO and paper_allowed=false.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("results/latest")


def main() -> None:
    (ROOT / "tables").mkdir(parents=True, exist_ok=True)
    (ROOT / "figures").mkdir(parents=True, exist_ok=True)
    (ROOT / "metrics.csv").write_text(
        "dataset,stream_type,prevalence,contamination_epsilon,baseline,memory_policy,calibration,image_auroc,aupr,ece,latency_ms,crd_lite,status\n"
        "MVTec AD|VisA,iid|bursty,0.05,0|0.01|0.05,RareCLIP|PatchCore|WinCLIP|AnomalyCLIP,default/SCS|FIFO|Reservoir|Prototype-EMA,none|temperature_scaling,TODO,TODO,TODO,TODO,TODO,placeholder_not_measured\n"
    )
    (ROOT / "tables" / "baseline_summary.tex").write_text(
        "% Placeholder table only. Do not present as measured findings.\n"
        "\\begin{table}[t]\n"
        "\\caption{P0 baseline summary (TODO: replace after real P0 run).}\n"
        "\\label{tab:baseline-summary}\n"
        "\\centering\n"
        "\\begin{tabular}{lccccc}\n"
        "\\hline\n"
        "Baseline & AUROC & AUPR & ECE & Latency & CRD-lite \\\\\n"
        "\\hline\n"
        "RareCLIP & TODO & TODO & TODO & TODO & TODO \\\\\n"
        "PatchCore & TODO & TODO & TODO & TODO & TODO \\\\\n"
        "WinCLIP & TODO & TODO & TODO & TODO & TODO \\\\\n"
        "AnomalyCLIP & TODO & TODO & TODO & TODO & TODO \\\\\n"
        "\\hline\n"
        "\\end{tabular}\n"
        "\\end{table}\n"
    )
    (ROOT / "figures" / "contamination_drop_placeholder.txt").write_text(
        "TODO placeholder for contamination drop figure.\n"
        "A real figure must be generated from results/latest/metrics.csv after P0 runs.\n"
    )
    manifest = json.loads((ROOT / "manifest.json").read_text()) if (ROOT / "manifest.json").exists() else {}
    manifest.update({
        "status": "placeholder",
        "scores_csv": "results/latest/scores.csv",
        "metrics_csv": "results/latest/metrics.csv",
        "tables": ["results/latest/tables/baseline_summary.tex"],
        "figures": ["results/latest/figures/contamination_drop_placeholder.txt"],
        "paper_allowed": False,
        "todo": [
            "Run real P0 experiments before replacing TODO result prose.",
            "Keep paper Results as TODO/placeholder while status is not final.",
        ],
    })
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(ROOT / "metrics.csv")
    print(ROOT / "manifest.json")


if __name__ == "__main__":
    main()
