#!/usr/bin/env python3
"""Generate and aggregate baseline mini-matrix smoke runs.

The mini-matrix is intentionally paper-ineligible: it exercises a small
baseline/category slice across stream types and contamination epsilons, then
aggregates measured smoke metrics without promoting them to paper results.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for mini-matrix config parsing") from error

DEFAULT_ROOT = Path("results/latest/mini_matrix")
CRD_LITE_FIELDS = [
    "dataset",
    "category",
    "stream_type",
    "baseline",
    "memory_policy",
    "calibration",
    "prevalence",
    "baseline_epsilon",
    "contamination_epsilon",
    "image_auroc_base",
    "image_auroc",
    "image_auroc_drop",
    "aupr_base",
    "aupr",
    "aupr_drop",
    "crd_lite",
    "status",
    "run_dir",
]


def slug(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace(".", "p").replace("-", "m")
    return re.sub(r"[^a-z0-9_]+", "_", text).strip("_") or "value"


def _load_config(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    if not isinstance(cfg, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return cfg


def _as_list(value: Any, default: list[Any]) -> list[Any]:
    if value is None:
        return list(default)
    if isinstance(value, list):
        return value
    return [value]


def _matrix_values(cfg: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    stream_types = _as_list(cfg.get("stream_types", cfg.get("stream_type")), ["iid"])
    epsilons = _as_list(cfg.get("contamination_epsilon"), [0])
    return stream_types, epsilons


def _run_id(baseline: Any, category: Any, stream_type: Any, epsilon: Any) -> str:
    return f"{slug(baseline)}_{slug(category)}_{slug(stream_type)}_eps_{slug(epsilon)}"


def default_aggregate_paths(cfg: dict[str, Any], root: Path) -> tuple[Path, Path]:
    baseline_slug = slug(cfg.get("baseline", "PatchCore"))
    category_slug = slug(cfg.get("category", "bottle"))
    outputs = cfg.get("outputs") or {}
    aggregate_metrics = Path(
        outputs.get("aggregate_metrics", root / f"metrics_{baseline_slug}_{category_slug}.csv")
    )
    aggregate_manifest = Path(
        outputs.get(
            "aggregate_manifest", root / f"manifest_{baseline_slug}_{category_slug}.json"
        )
    )
    return aggregate_metrics, aggregate_manifest


def default_crd_lite_path(cfg: dict[str, Any], root: Path) -> Path:
    baseline_slug = slug(cfg.get("baseline", "PatchCore"))
    category_slug = slug(cfg.get("category", "bottle"))
    outputs = cfg.get("outputs") or {}
    return Path(
        outputs.get(
            "crd_lite_summary", root / f"crd_lite_{baseline_slug}_{category_slug}.csv"
        )
    )


def generate_run_configs(matrix_config: Path) -> list[Path]:
    cfg = _load_config(matrix_config)
    baseline = cfg.get("baseline", "PatchCore")
    baseline_path = cfg.get("baseline_path", "external/patchcore-inspection")
    dataset = cfg.get("dataset", "MVTec AD")
    dataset_root = cfg.get("dataset_root", "data/mvtec_ad")
    category = cfg.get("category", "bottle")
    prevalence = cfg.get("prevalence", 0.05)
    stream_cfg = cfg.get("stream") or {}
    outputs = cfg.get("outputs") or {}
    root = Path(outputs.get("root", DEFAULT_ROOT))
    configs_dir = root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    baseline_slug = slug(baseline)
    category_slug = slug(category)
    stream_types, epsilons = _matrix_values(cfg)
    provenance = cfg.get("provenance") or {}

    paths: list[Path] = []
    for stream_type in stream_types:
        for epsilon in epsilons:
            run_id = _run_id(baseline_slug, category_slug, stream_type, epsilon)
            run_dir = root / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            run_cfg: dict[str, Any] = {
                "baseline": baseline,
                "baseline_path": baseline_path,
                "dataset": dataset,
                "dataset_root": dataset_root,
                "category": category,
                "stream_type": stream_type,
                "prevalence": prevalence,
                "contamination_epsilon": epsilon,
                "stream": {
                    "path": str(run_dir / "stream.json"),
                    "seed": stream_cfg.get("seed", 0),
                    "length": stream_cfg.get("length"),
                    "burst_length": stream_cfg.get("burst_length", 1),
                },
                "outputs": {
                    "scores_csv": str(run_dir / "scores.csv"),
                    "latest_run": str(run_dir / "latest_run.json"),
                    "manifest": str(run_dir / "manifest.json"),
                },
            }
            if provenance:
                run_cfg["provenance"] = provenance
            path = configs_dir / f"{run_id}.yaml"
            path.write_text(yaml.safe_dump(run_cfg, sort_keys=False), encoding="utf-8")
            paths.append(path)
    return paths


def run_dir_for_config(config_path: Path) -> Path:
    return config_path.parent.parent / config_path.stem


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _format_number(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "NA"
    return f"{value:.6f}"


def _epsilon(row: dict[str, str]) -> float | None:
    return _float_or_none(row.get("contamination_epsilon"))


def _crd_group_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row.get("dataset", "unknown"),
        row.get("stream_type", "unknown"),
        row.get("baseline", "unknown"),
        row.get("memory_policy", "unknown"),
        row.get("calibration", "unknown"),
        row.get("prevalence", "unknown"),
    )


def compute_crd_lite(
    rows: list[dict[str, str]], *, category: str
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Compute contamination robustness degradation against epsilon=0 rows.

    CRD-lite is a signed smoke diagnostic:

        mean((AUROC at ε=0 - AUROC at ε), (AUPR at ε=0 - AUPR at ε))

    Positive values indicate degradation under contamination, zero indicates no
    measured drop, and negative values indicate an improvement in the measured
    smoke metric. The value is derived only from measured aggregate rows and is
    not a paper-ready full-P0 metric.
    """
    baselines: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}
    for row in rows:
        epsilon = _epsilon(row)
        if epsilon is not None and math.isclose(epsilon, 0.0):
            baselines[_crd_group_key(row)] = row

    summary_rows: list[dict[str, str]] = []
    crd_by_run_dir: dict[str, str] = {}
    for row in rows:
        baseline_row = baselines.get(_crd_group_key(row))
        auroc_base = _float_or_none(
            baseline_row.get("image_auroc") if baseline_row else None
        )
        aupr_base = _float_or_none(baseline_row.get("aupr") if baseline_row else None)
        auroc = _float_or_none(row.get("image_auroc"))
        aupr = _float_or_none(row.get("aupr"))

        auroc_drop = None if auroc_base is None or auroc is None else auroc_base - auroc
        aupr_drop = None if aupr_base is None or aupr is None else aupr_base - aupr
        drops = [drop for drop in [auroc_drop, aupr_drop] if drop is not None]
        crd = sum(drops) / len(drops) if drops else None

        crd_value = _format_number(crd)
        run_dir = row.get("run_dir", "")
        if run_dir:
            crd_by_run_dir[run_dir] = crd_value

        summary_rows.append(
            {
                "dataset": row.get("dataset", "unknown"),
                "category": category,
                "stream_type": row.get("stream_type", "unknown"),
                "baseline": row.get("baseline", "unknown"),
                "memory_policy": row.get("memory_policy", "unknown"),
                "calibration": row.get("calibration", "unknown"),
                "prevalence": row.get("prevalence", "unknown"),
                "baseline_epsilon": "0.0",
                "contamination_epsilon": row.get("contamination_epsilon", "unknown"),
                "image_auroc_base": _format_number(auroc_base),
                "image_auroc": _format_number(auroc),
                "image_auroc_drop": _format_number(auroc_drop),
                "aupr_base": _format_number(aupr_base),
                "aupr": _format_number(aupr),
                "aupr_drop": _format_number(aupr_drop),
                "crd_lite": crd_value,
                "status": (
                    "derived_smoke"
                    if row.get("status") == "measured_smoke" and crd is not None
                    else "not_available"
                ),
                "run_dir": run_dir,
            }
        )
    return summary_rows, crd_by_run_dir


def write_crd_lite_summary(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CRD_LITE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def aggregate_metrics(matrix_config: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    cfg = _load_config(matrix_config)
    outputs = cfg.get("outputs") or {}
    root = Path(outputs.get("root", DEFAULT_ROOT))
    aggregate_metrics, aggregate_manifest = default_aggregate_paths(cfg, root)
    crd_lite_summary = default_crd_lite_path(cfg, root)
    baseline = cfg.get("baseline", "PatchCore")
    category = cfg.get("category", "bottle")
    stream_types, epsilons = _matrix_values(cfg)

    rows: list[dict[str, str]] = []
    for stream_type in stream_types:
        for epsilon in epsilons:
            run_id = _run_id(baseline, category, stream_type, epsilon)
            metrics_path = root / run_id / "metrics.csv"
            if not metrics_path.exists():
                raise SystemExit(f"Missing mini-matrix metrics: {metrics_path}")
            with metrics_path.open(newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    row = dict(row)
                    row["run_dir"] = str(metrics_path.parent)
                    rows.append(row)

    if not rows:
        raise SystemExit(f"No mini-matrix metrics found under {root} for {slug(baseline)}")

    crd_rows, crd_by_run_dir = compute_crd_lite(rows, category=str(category))
    for row in rows:
        row["crd_lite"] = crd_by_run_dir.get(row.get("run_dir", ""), "NA")

    fieldnames = list(rows[0].keys())
    aggregate_metrics.parent.mkdir(parents=True, exist_ok=True)
    with aggregate_metrics.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write_crd_lite_summary(crd_lite_summary, crd_rows)

    manifest = {
        "status": f"{slug(baseline)}_mini_matrix_complete",
        "paper_allowed": False,
        "baseline": str(baseline),
        "dataset": str(cfg.get("dataset", "MVTec AD")),
        "category": str(category),
        "stream_types": [str(value) for value in stream_types],
        "contamination_epsilon": [str(value) for value in epsilons],
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(rows),
        "runs": rows,
        "crd_lite": crd_rows,
        "notes": (
            "Baseline mini-matrix smoke results for pipeline validation only; "
            "CRD-lite is derived from epsilon=0 metric drops and is not full P0 "
            "or paper gate."
        ),
    }
    aggregate_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return aggregate_metrics, aggregate_manifest, rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="write per-run smoke configs")
    prepare.add_argument("matrix_config", type=Path)

    aggregate = subparsers.add_parser("aggregate", help="aggregate per-run metrics")
    aggregate.add_argument("matrix_config", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        for path in generate_run_configs(args.matrix_config):
            print(path)
    elif args.command == "aggregate":
        aggregate_metrics_path, aggregate_manifest_path, _ = aggregate_metrics(
            args.matrix_config
        )
        print(aggregate_metrics_path)
        print(aggregate_manifest_path)


if __name__ == "__main__":
    main()
