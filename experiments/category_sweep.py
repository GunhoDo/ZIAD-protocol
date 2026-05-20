#!/usr/bin/env python3
"""Prepare and aggregate small category quick sweeps.

A category quick sweep runs the existing single-category mini-matrix helper over
multiple baselines and MVTec categories, then combines the aggregate smoke
outputs. It remains paper-ineligible and is intended to catch category-specific
path/schema/runtime issues before full P0.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/category_sweep.py ...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for category sweep config parsing") from error

from experiments import mini_matrix

DEFAULT_ROOT = Path("results/latest/category_quick_sweep")


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


def _baseline_entries(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    entries = cfg.get("baselines")
    if entries is None:
        entries = [
            {
                "name": cfg.get("baseline", "PatchCore"),
                "baseline_path": cfg.get("baseline_path", "external/patchcore-inspection"),
                "provenance": cfg.get("provenance") or {},
            }
        ]
    if not isinstance(entries, list) or not entries:
        raise SystemExit("category sweep requires at least one baseline entry")
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise SystemExit("baseline entries must be mappings with a name")
        normalized.append(dict(entry))
    return normalized


def _matrix_config_path(root: Path, baseline: str, category: str) -> Path:
    return root / "configs" / f"{mini_matrix.slug(baseline)}_{mini_matrix.slug(category)}_matrix.yaml"


def _matrix_output_root(root: Path, baseline: str, category: str) -> Path:
    return root / "details" / f"{mini_matrix.slug(baseline)}_{mini_matrix.slug(category)}"


def iter_matrix_specs(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = cfg.get("outputs") or {}
    root = Path(outputs.get("root", DEFAULT_ROOT))
    categories = _as_list(cfg.get("categories", cfg.get("category")), ["bottle"])
    specs: list[dict[str, Any]] = []
    for baseline in _baseline_entries(cfg):
        name = str(baseline["name"])
        for category in categories:
            category_str = str(category)
            detail_root = _matrix_output_root(root, name, category_str)
            specs.append(
                {
                    "baseline": name,
                    "baseline_path": baseline.get("baseline_path", ""),
                    "category": category_str,
                    "config_path": _matrix_config_path(root, name, category_str),
                    "detail_root": detail_root,
                    "aggregate_metrics": detail_root
                    / f"metrics_{mini_matrix.slug(name)}_{mini_matrix.slug(category_str)}.csv",
                    "aggregate_manifest": detail_root
                    / f"manifest_{mini_matrix.slug(name)}_{mini_matrix.slug(category_str)}.json",
                    "crd_lite_summary": detail_root
                    / f"crd_lite_{mini_matrix.slug(name)}_{mini_matrix.slug(category_str)}.csv",
                    "provenance": baseline.get("provenance") or {},
                }
            )
    return specs


def generate_matrix_configs(sweep_config: Path) -> list[Path]:
    cfg = _load_config(sweep_config)
    dataset = cfg.get("dataset", "MVTec AD")
    dataset_root = cfg.get("dataset_root", "data/mvtec_ad")
    prevalence = cfg.get("prevalence", 0.05)
    stream_types = _as_list(cfg.get("stream_types", cfg.get("stream_type")), ["iid"])
    epsilons = _as_list(cfg.get("contamination_epsilon"), [0])
    stream_cfg = cfg.get("stream") or {}

    paths: list[Path] = []
    for spec in iter_matrix_specs(cfg):
        matrix_cfg: dict[str, Any] = {
            "baseline": spec["baseline"],
            "baseline_path": spec["baseline_path"],
            "dataset": dataset,
            "dataset_root": dataset_root,
            "category": spec["category"],
            "prevalence": prevalence,
            "stream_types": stream_types,
            "contamination_epsilon": epsilons,
            "stream": {
                "seed": stream_cfg.get("seed", 0),
                "length": stream_cfg.get("length"),
                "burst_length": stream_cfg.get("burst_length", 1),
            },
            "outputs": {
                "root": str(spec["detail_root"]),
                "aggregate_metrics": str(spec["aggregate_metrics"]),
                "aggregate_manifest": str(spec["aggregate_manifest"]),
                "crd_lite_summary": str(spec["crd_lite_summary"]),
            },
        }
        if spec["provenance"]:
            matrix_cfg["provenance"] = spec["provenance"]
        path = spec["config_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(matrix_cfg, sort_keys=False), encoding="utf-8")
        paths.append(path)
    return paths


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing category sweep artifact: {path}")
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise SystemExit(f"No rows to write: {path}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _insert_category(row: dict[str, str], category: str) -> dict[str, str]:
    if "category" in row:
        row["category"] = row.get("category") or category
        return row
    result: dict[str, str] = {}
    for key, value in row.items():
        result[key] = value
        if key == "dataset":
            result["category"] = category
    if "category" not in result:
        result["category"] = category
    return result


def default_output_paths(cfg: dict[str, Any]) -> tuple[Path, Path, Path]:
    outputs = cfg.get("outputs") or {}
    root = Path(outputs.get("root", DEFAULT_ROOT))
    aggregate_metrics = Path(
        outputs.get("aggregate_metrics", root / "metrics_mvtec_category_quick_sweep.csv")
    )
    aggregate_manifest = Path(
        outputs.get("aggregate_manifest", root / "manifest_mvtec_category_quick_sweep.json")
    )
    crd_lite_summary = Path(
        outputs.get("crd_lite_summary", root / "crd_lite_mvtec_category_quick_sweep.csv")
    )
    return aggregate_metrics, aggregate_manifest, crd_lite_summary


def aggregate_sweep(sweep_config: Path) -> tuple[Path, Path, Path, list[dict[str, str]]]:
    cfg = _load_config(sweep_config)
    outputs = cfg.get("outputs") or {}
    aggregate_metrics, aggregate_manifest, crd_lite_summary = default_output_paths(cfg)
    metric_rows: list[dict[str, str]] = []
    crd_rows: list[dict[str, str]] = []
    manifests: list[dict[str, Any]] = []

    for spec in iter_matrix_specs(cfg):
        category = str(spec["category"])
        for row in _read_csv(Path(spec["aggregate_metrics"])):
            metric_rows.append(_insert_category(row, category))
        for row in _read_csv(Path(spec["crd_lite_summary"])):
            crd_rows.append(_insert_category(row, category))
        manifest_path = Path(spec["aggregate_manifest"])
        if not manifest_path.exists():
            raise SystemExit(f"Missing category sweep manifest: {manifest_path}")
        manifests.append(json.loads(manifest_path.read_text()))

    _write_csv(aggregate_metrics, metric_rows)
    _write_csv(crd_lite_summary, crd_rows)

    manifest = {
        "status": str(outputs.get("status", "category_quick_sweep_complete")),
        "paper_allowed": False,
        "dataset": str(cfg.get("dataset", "MVTec AD")),
        "categories": [str(value) for value in _as_list(cfg.get("categories", cfg.get("category")), ["bottle"])],
        "baselines": [entry["name"] for entry in _baseline_entries(cfg)],
        "stream_types": [str(value) for value in _as_list(cfg.get("stream_types", cfg.get("stream_type")), ["iid"])],
        "contamination_epsilon": [str(value) for value in _as_list(cfg.get("contamination_epsilon"), [0])],
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(metric_rows),
        "crd_lite_row_count": len(crd_rows),
        "matrix_manifests": manifests,
        "notes": str(
            outputs.get(
                "notes",
                "Category sweep smoke evidence only; not full P0 or paper gate.",
            )
        ),
    }
    aggregate_manifest.parent.mkdir(parents=True, exist_ok=True)
    aggregate_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return aggregate_metrics, aggregate_manifest, crd_lite_summary, metric_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="write per-category matrix configs")
    prepare.add_argument("sweep_config", type=Path)

    aggregate = subparsers.add_parser("aggregate", help="combine per-category aggregates")
    aggregate.add_argument("sweep_config", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        for path in generate_matrix_configs(args.sweep_config):
            print(path)
    elif args.command == "aggregate":
        aggregate_metrics, aggregate_manifest, crd_lite_summary, _ = aggregate_sweep(
            args.sweep_config
        )
        print(aggregate_metrics)
        print(aggregate_manifest)
        print(crd_lite_summary)


if __name__ == "__main__":
    main()
