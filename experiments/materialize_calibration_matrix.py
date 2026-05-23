#!/usr/bin/env python3
"""Materialize calibration matrix rows from existing measured smoke scores.

This helper is intentionally paper-ineligible. It reuses measured score CSVs
from an existing uncalibrated category sweep, applies deterministic calibration
postprocessing for requested calibration variants, then runs the existing
mini/category aggregation code. It does not create model scores from scratch.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for calibration matrix materialization") from error

from experiments import category_sweep, mini_matrix
from experiments.calibration import apply_calibration_from_config
from experiments.evaluate import evaluate

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


def _load_config(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    if not isinstance(cfg, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return cfg


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing source artifact: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON artifact must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_specs_by_key(source_cfg: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    specs: dict[tuple[str, str], dict[str, Any]] = {}
    for spec in category_sweep.iter_matrix_specs(source_cfg):
        key = (mini_matrix.slug(spec["baseline"]), mini_matrix.slug(spec["category"]))
        specs[key] = spec
    return specs


def _require_measured_scores(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Missing source scores: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SCORE_FIELDS:
            raise SystemExit(
                f"Source scores header mismatch. Expected {SCORE_FIELDS}, got {reader.fieldnames}"
            )
        rows = list(reader)
    measured = [row for row in rows if row.get("status") == "measured"]
    if not measured:
        raise SystemExit(f"Source scores contain no measured rows: {path}")
    unknown = sorted({row.get("status", "") for row in rows} - {"measured", "placeholder_not_measured"})
    if unknown:
        raise SystemExit(f"Source scores contain unknown status values {unknown}: {path}")


def _source_run_dir(source_spec: dict[str, Any], target_run_cfg: dict[str, Any]) -> Path:
    run_id = mini_matrix._run_id(  # noqa: SLF001 - intentional same-contract reuse.
        target_run_cfg["baseline"],
        target_run_cfg["category"],
        target_run_cfg["stream_type"],
        target_run_cfg["contamination_epsilon"],
        "none",
        include_calibration=False,
    )
    return Path(source_spec["detail_root"]) / run_id


def _apply_stream_provenance(stream_path: Path, provenance: dict[str, Any]) -> None:
    stream_payload = _read_json(stream_path)
    metadata = stream_payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise SystemExit(f"Stream metadata must be an object: {stream_path}")
    for key in ["scoring_mode", "latency_semantics", "training_source", "stream_source"]:
        if key in provenance:
            metadata[key] = provenance[key]
    _write_json(stream_path, stream_payload)


def _build_latest_run(
    source_latest_run: Path,
    target_run_cfg: dict[str, Any],
    stream_path: Path,
    calibration_metadata: dict[str, Any],
) -> dict[str, Any]:
    latest = _read_json(source_latest_run)
    provenance = target_run_cfg.get("provenance") or {}
    latest.update(
        {
            "stream_path": str(stream_path),
            "stream_type": str(target_run_cfg["stream_type"]),
            "prevalence": float(target_run_cfg["prevalence"]),
            "contamination_epsilon": float(target_run_cfg["contamination_epsilon"]),
            "memory_policy": str(target_run_cfg.get("memory_policy", "default/SCS")),
            "calibration": str(target_run_cfg.get("calibration", "none")),
            "stream_seed": int((target_run_cfg.get("stream") or {}).get("seed", 0)),
            "stream_length": (target_run_cfg.get("stream") or {}).get("length"),
            "burst_length": int((target_run_cfg.get("stream") or {}).get("burst_length", 1)),
            "scoring_mode": provenance.get("scoring_mode", latest.get("scoring_mode")),
            "latency_semantics": provenance.get(
                "latency_semantics", latest.get("latency_semantics")
            ),
            "training_source": provenance.get("training_source", latest.get("training_source")),
            "stream_source": provenance.get("stream_source", latest.get("stream_source")),
            "calibration_metadata": calibration_metadata,
            "command": "python3 experiments/materialize_calibration_matrix.py",
            "timestamp": _utc_now(),
            "paper_allowed": False,
            "notes": (
                "Paper-ineligible smoke matrix row materialized from existing "
                "measured scores; calibration variants are deterministic "
                "postprocessing only."
            ),
        }
    )
    return latest


def materialize_run(source_spec: dict[str, Any], target_run_config: Path) -> str:
    target_run_cfg = _load_config(target_run_config)
    source_dir = _source_run_dir(source_spec, target_run_cfg)
    source_scores = source_dir / "scores.csv"
    source_stream = source_dir / "stream.json"
    source_latest = source_dir / "latest_run.json"
    _require_measured_scores(source_scores)
    if not source_stream.exists():
        raise SystemExit(f"Missing source stream: {source_stream}")
    if not source_latest.exists():
        raise SystemExit(f"Missing source latest_run: {source_latest}")

    outputs = target_run_cfg.get("outputs") or {}
    scores_csv = Path(outputs["scores_csv"])
    latest_run = Path(outputs["latest_run"])
    manifest = Path(outputs["manifest"])
    metrics_csv = scores_csv.parent / "metrics.csv"
    stream_path = Path((target_run_cfg.get("stream") or {})["path"])

    scores_csv.parent.mkdir(parents=True, exist_ok=True)
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_scores, scores_csv)
    shutil.copyfile(source_stream, stream_path)
    _apply_stream_provenance(stream_path, target_run_cfg.get("provenance") or {})

    calibration = str(target_run_cfg.get("calibration", "none"))
    calibration_metadata: dict[str, Any] = {}
    if calibration != "none":
        calibration_metadata_path = scores_csv.with_name(f"{scores_csv.stem}_calibration.json")
        calibration_metadata = apply_calibration_from_config(
            scores_csv,
            target_run_cfg,
            metadata_output=calibration_metadata_path,
        )

    _write_json(
        latest_run,
        _build_latest_run(source_latest, target_run_cfg, stream_path, calibration_metadata),
    )
    _write_json(manifest, {"status": "first_success_a", "paper_allowed": False})
    evaluate(scores_csv, latest_run, metrics_csv, manifest)
    return calibration


def materialize_category_sweep(
    source_sweep_config: Path,
    target_sweep_config: Path,
) -> dict[str, int]:
    source_cfg = _load_config(source_sweep_config)
    source_specs = _source_specs_by_key(source_cfg)

    matrix_count = 0
    run_count = 0
    calibrated_count = 0
    target_matrix_configs = category_sweep.generate_matrix_configs(target_sweep_config)
    for target_matrix_config in target_matrix_configs:
        matrix_cfg = _load_config(target_matrix_config)
        key = (mini_matrix.slug(matrix_cfg["baseline"]), mini_matrix.slug(matrix_cfg["category"]))
        source_spec = source_specs.get(key)
        if source_spec is None:
            raise SystemExit(
                "Missing source matrix for "
                f"baseline={matrix_cfg['baseline']} category={matrix_cfg['category']}"
            )
        for run_config in mini_matrix.generate_run_configs(target_matrix_config):
            calibration = materialize_run(source_spec, run_config)
            run_count += 1
            if calibration != "none":
                calibrated_count += 1
        mini_matrix.aggregate_metrics(target_matrix_config)
        matrix_count += 1

    category_sweep.aggregate_sweep(target_sweep_config)
    return {
        "matrix_configs": matrix_count,
        "materialized_runs": run_count,
        "calibrated_runs": calibrated_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sweep-config", required=True, type=Path)
    parser.add_argument("--target-sweep-config", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = materialize_category_sweep(args.source_sweep_config, args.target_sweep_config)
    for key, value in summary.items():
        print(f"{key} {value}")


if __name__ == "__main__":
    main()
