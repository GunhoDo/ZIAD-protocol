#!/usr/bin/env python3
"""Evaluate common score CSV outputs into lightweight metric artifacts.

The evaluator is safety-first: placeholder score files keep placeholder metric
artifacts, while measured score rows produce derived metrics only from the
provided scores. It never fabricates missing metrics.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

ROOT = Path("results/latest")
SCORE_FIELDS = [
    "stream_index",
    "image_path",
    "label",
    "category",
    "anomaly_score",
    "latency_ms",
    "peak_vram_mb",
    "status",
]
METRIC_FIELDS = [
    "dataset",
    "stream_type",
    "prevalence",
    "contamination_epsilon",
    "baseline",
    "memory_policy",
    "calibration",
    "image_auroc",
    "aupr",
    "ece",
    "latency_ms",
    "crd_lite",
    "status",
]
PLACEHOLDER_ROW = {
    "dataset": "MVTec AD|VisA",
    "stream_type": "iid|bursty",
    "prevalence": "0.05",
    "contamination_epsilon": "0|0.01|0.05",
    "baseline": "RareCLIP|PatchCore|WinCLIP|AnomalyCLIP",
    "memory_policy": "default/SCS|FIFO|Reservoir|Prototype-EMA",
    "calibration": "none|temperature_scaling",
    "image_auroc": "TODO",
    "aupr": "TODO",
    "ece": "TODO",
    "latency_ms": "TODO",
    "crd_lite": "TODO",
    "status": "placeholder_not_measured",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _format_metric(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "NA"
    return f"{value:.6f}"


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def _load_scores(scores_csv: Path) -> list[dict[str, str]]:
    if not scores_csv.exists():
        raise FileNotFoundError(f"scores.csv not found: {scores_csv}")
    with scores_csv.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SCORE_FIELDS:
            raise RuntimeError(
                "scores.csv header mismatch.\n"
                f"  Expected: {SCORE_FIELDS}\n"
                f"  Got:      {reader.fieldnames}"
            )
        return list(reader)


def _measured_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    statuses = {row.get("status", "") for row in rows}
    allowed = {"measured", "placeholder_not_measured"}
    unknown = sorted(statuses - allowed)
    if unknown:
        raise RuntimeError(f"Unknown score row status value(s): {unknown}")
    return [row for row in rows if row.get("status") == "measured"]


def _binary_labels(rows: list[dict[str, str]]) -> list[int]:
    labels = [int(row["label"]) for row in rows]
    invalid = sorted(set(labels) - {0, 1})
    if invalid:
        raise RuntimeError(f"Labels must be binary 0/1, got: {invalid}")
    return labels


def _float_column(rows: list[dict[str, str]], column: str) -> list[float]:
    return [float(row[column]) for row in rows]


def _image_auroc(labels: list[int], scores: list[float]) -> float | None:
    if len(set(labels)) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise RuntimeError("scikit-learn is required to compute AUROC") from error
    return float(roc_auc_score(labels, scores))


def _aupr(labels: list[int], scores: list[float]) -> float | None:
    if len(set(labels)) < 2:
        return None
    try:
        from sklearn.metrics import average_precision_score
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise RuntimeError("scikit-learn is required to compute AUPR") from error
    return float(average_precision_score(labels, scores))


def _minmax_probabilities(scores: list[float]) -> list[float] | None:
    lo = min(scores)
    hi = max(scores)
    if math.isclose(lo, hi):
        return None
    return [(score - lo) / (hi - lo) for score in scores]


def _ece(labels: list[int], scores: list[float], n_bins: int = 10) -> float | None:
    """Compute binary ECE after min-max normalizing anomaly scores.

    PatchCore emits uncalibrated anomaly scores rather than probabilities. For
    smoke tracking, ECE is therefore computed on min-max normalized scores and
    should be treated as a diagnostic, not paper-ready calibration evidence.
    """
    probabilities = _minmax_probabilities(scores)
    if probabilities is None:
        return None

    total = len(labels)
    error = 0.0
    for bin_index in range(n_bins):
        lower = bin_index / n_bins
        upper = (bin_index + 1) / n_bins
        if bin_index == n_bins - 1:
            indices = [i for i, p in enumerate(probabilities) if lower <= p <= upper]
        else:
            indices = [i for i, p in enumerate(probabilities) if lower <= p < upper]
        if not indices:
            continue
        confidence = sum(probabilities[i] for i in indices) / len(indices)
        observed_rate = sum(labels[i] for i in indices) / len(indices)
        error += (len(indices) / total) * abs(confidence - observed_rate)
    return error


def compute_metric_row(
    score_rows: list[dict[str, str]], latest_run: dict[str, Any] | None = None
) -> dict[str, str]:
    latest_run = latest_run or {}
    measured = _measured_rows(score_rows)
    if not measured:
        return dict(PLACEHOLDER_ROW)

    labels = _binary_labels(measured)
    scores = _float_column(measured, "anomaly_score")
    latencies = _float_column(measured, "latency_ms")

    return {
        "dataset": str(latest_run.get("dataset", "unknown")),
        "stream_type": str(latest_run.get("stream_type", "unknown")),
        "prevalence": str(latest_run.get("prevalence", "unknown")),
        "contamination_epsilon": str(
            latest_run.get("contamination_epsilon", "unknown")
        ),
        "baseline": str(latest_run.get("baseline", "unknown")),
        "memory_policy": str(latest_run.get("memory_policy", "default/SCS")),
        "calibration": str(latest_run.get("calibration", "none")),
        "image_auroc": _format_metric(_image_auroc(labels, scores)),
        "aupr": _format_metric(_aupr(labels, scores)),
        "ece": _format_metric(_ece(labels, scores)),
        "latency_ms": _format_metric(_mean(latencies)),
        "crd_lite": "NA",
        "status": "measured_smoke",
    }


def write_metrics_csv(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def write_summary_table(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if row["status"] == "placeholder_not_measured":
        body = (
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
    else:
        body = (
            "% Smoke-only measured table. paper_allowed remains false.\n"
            "\\begin{table}[t]\n"
            "\\caption{PatchCore smoke metrics on MVTec AD bottle "
            "(non-final, paper-ineligible).}\n"
            "\\label{tab:patchcore-smoke}\n"
            "\\centering\n"
            "\\begin{tabular}{lccccc}\n"
            "\\hline\n"
            "Baseline & AUROC & AUPR & ECE & Latency & CRD-lite \\\\\n"
            "\\hline\n"
            f"{row['baseline']} & {row['image_auroc']} & {row['aupr']} & "
            f"{row['ece']} & {row['latency_ms']} & {row['crd_lite']} \\\\\n"
            "\\hline\n"
            "\\end{tabular}\n"
            "\\end{table}\n"
        )
    path.write_text(body)


def update_manifest(path: Path, row: dict[str, str]) -> None:
    manifest = _read_json(path)
    status = "placeholder" if row["status"] == "placeholder_not_measured" else "evaluated_smoke"
    manifest.update(
        {
            "status": status,
            "scores_csv": "results/latest/scores.csv",
            "metrics_csv": "results/latest/metrics.csv",
            "tables": ["results/latest/tables/baseline_summary.tex"],
            "figures": ["results/latest/figures/contamination_drop_placeholder.txt"],
            "paper_allowed": False,
            "todo": [
                "Run full P0 experiments before replacing TODO result prose.",
                "Promote to paper_allowed=true only after measured outputs "
                "are produced and reviewed.",
            ],
        }
    )
    _write_json(path, manifest)


def evaluate(
    scores_csv: Path, latest_run: Path, output_csv: Path, manifest: Path
) -> dict[str, str]:
    rows = _load_scores(scores_csv)
    latest = _read_json(latest_run)
    metric_row = compute_metric_row(rows, latest)
    artifact_root = output_csv.parent
    write_metrics_csv(output_csv, metric_row)
    write_summary_table(artifact_root / "tables" / "baseline_summary.tex", metric_row)
    (artifact_root / "figures").mkdir(parents=True, exist_ok=True)
    (artifact_root / "figures" / "contamination_drop_placeholder.txt").write_text(
        "TODO placeholder for contamination drop figure.\n"
        "CRD-lite requires comparable runs across contamination epsilons.\n"
    )
    update_manifest(manifest, metric_row)
    return metric_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-csv", type=Path, default=ROOT / "scores.csv")
    parser.add_argument("--latest-run", type=Path, default=ROOT / "latest_run.json")
    parser.add_argument("--output", type=Path, default=ROOT / "metrics.csv")
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifest.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    row = evaluate(args.scores_csv, args.latest_run, args.output, args.manifest)
    print(args.output)
    print(args.manifest)
    print(f"status={row['status']}")


if __name__ == "__main__":
    main()
