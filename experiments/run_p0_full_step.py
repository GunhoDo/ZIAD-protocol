#!/usr/bin/env python3
"""Execute or dry-run one compact full-P0 aggregate step.

This is the single-step boundary for the future reviewed P0 run. It resolves
one step from `results/latest/p0_full/execution_plan.json`, validates that every
declared output stays under `results/latest/p0_full/`, and keeps all paper gates
closed. Production execution is intentionally guarded to explicitly validated
steps; use `--dry-run` to inspect any selected step without producing outputs.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

if __package__ in {None, ""}:  # Allow `python3 experiments/run_p0_full_step.py ...`.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for full-P0 step execution") from error

from experiments import evaluate, make_streams, mini_matrix
from experiments.calibration import apply_calibration_from_config

DEFAULT_PLAN = Path("results/latest/p0_full/execution_plan.json")
FULL_OUTPUT_ROOT = Path("results/latest/p0_full")
REQUIRED_METADATA = {
    "run_tier": "p0_full",
    "paper_allowed": False,
    "claim_allowed": False,
    "review_status": "not_reviewed",
}
DEFAULT_DATASET_ROOTS = {
    "MVTec AD": "data/mvtec_ad",
    "VisA": "data/visa",
}
DEFAULT_BASELINE_PATHS = {
    "PatchCore": "external/patchcore-inspection",
    "WinCLIP": "external/WinClip",
    "AnomalyCLIP": "external/AnomalyCLIP",
    "RareCLIP": "external/RareCLIP",
}
DEFAULT_VALIDATION_CATEGORIES = {
    "MVTec AD": "bottle",
    "VisA": "candle",
}
PATCHCORE_PRODUCTION_VALIDATION_SAMPLER_PERCENTAGE = 0.001
ALLOWED_PRODUCTION_STEP_IDS = {
    "mvtec_ad:patchcore:default_scs:none",
    "mvtec_ad:patchcore:default_scs:temperature_scaling",
    "mvtec_ad:patchcore:reservoir:none",
    "mvtec_ad:patchcore:reservoir:temperature_scaling",
    "mvtec_ad:anomalyclip:default_no_memory:none",
    "mvtec_ad:anomalyclip:default_no_memory:temperature_scaling",
    "mvtec_ad:rareclip:default_scs:none",
    "mvtec_ad:rareclip:default_scs:temperature_scaling",
    "mvtec_ad:rareclip:reservoir:none",
    "mvtec_ad:rareclip:reservoir:temperature_scaling",
    "mvtec_ad:winclip:default_no_memory:none",
    "mvtec_ad:winclip:default_no_memory:temperature_scaling",
    "visa:anomalyclip:default_no_memory:none",
    "visa:anomalyclip:default_no_memory:temperature_scaling",
    "visa:patchcore:default_scs:none",
    "visa:patchcore:default_scs:temperature_scaling",
    "visa:patchcore:reservoir:none",
    "visa:patchcore:reservoir:temperature_scaling",
    "visa:rareclip:default_scs:none",
    "visa:rareclip:default_scs:temperature_scaling",
    "visa:rareclip:reservoir:none",
    "visa:rareclip:reservoir:temperature_scaling",
    "visa:winclip:default_no_memory:none",
    "visa:winclip:default_no_memory:temperature_scaling",
}
CommandRunner = Callable[[list[str]], int]


class FullP0StepError(ValueError):
    """Raised when a full-P0 step is malformed or cannot be selected."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FullP0StepError(f"Missing full-P0 execution plan: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise FullP0StepError(f"Execution plan must be a JSON object: {path}")
    return payload


def _as_posix(path: Path | str) -> str:
    return Path(str(path)).as_posix()


def _repo_path(path: Path | str) -> Path:
    candidate = Path(str(path))
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _is_under_full_root(path: Path | str) -> bool:
    value = _as_posix(path)
    root = FULL_OUTPUT_ROOT.as_posix().rstrip("/") + "/"
    return value == FULL_OUTPUT_ROOT.as_posix() or value.startswith(root)


def load_plan(path: Path = DEFAULT_PLAN) -> dict[str, Any]:
    plan = _load_json(path)
    _enforce_metadata(plan, context="execution plan")
    if plan.get("source_tier") == "smoke":
        raise FullP0StepError("full-P0 execution plan source_tier must not be smoke")
    if plan.get("output_root") and not _is_under_full_root(str(plan["output_root"])):
        raise FullP0StepError(f"full-P0 plan output_root is outside {FULL_OUTPUT_ROOT}")
    if not isinstance(plan.get("steps"), list):
        raise FullP0StepError("full-P0 execution plan must contain a steps list")
    return plan


def _enforce_metadata(payload: dict[str, Any], *, context: str) -> None:
    for key, expected in REQUIRED_METADATA.items():
        if payload.get(key) != expected:
            raise FullP0StepError(f"{context} {key} must be {expected!r}")


def resolve_step(plan: dict[str, Any], selector: str) -> tuple[int, dict[str, Any]]:
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise FullP0StepError("full-P0 execution plan contains no steps")

    try:
        index = int(selector)
    except ValueError:
        matches = [
            (idx, step)
            for idx, step in enumerate(steps)
            if isinstance(step, dict) and step.get("step_id") == selector
        ]
        if not matches:
            raise FullP0StepError(f"Unknown full-P0 step id: {selector}")
        return matches[0]

    if index < 0 or index >= len(steps):
        raise FullP0StepError(f"Full-P0 step index out of range: {index}")
    step = steps[index]
    if not isinstance(step, dict):
        raise FullP0StepError(f"Full-P0 step at index {index} is not an object")
    return index, step


def validate_step_contract(
    step: dict[str, Any],
    *,
    output_root: Path | None = None,
) -> None:
    _enforce_metadata(step, context=f"step {step.get('step_id', '<unknown>')}")
    if step.get("source_tier") == "smoke":
        raise FullP0StepError("full-P0 step source_tier must not be smoke")

    declared_output_root = step.get("output_root")
    if declared_output_root is not None and not _is_under_full_root(
        str(declared_output_root)
    ):
        raise FullP0StepError(
            f"step output_root is outside {FULL_OUTPUT_ROOT}: {declared_output_root}"
        )
    if output_root is not None:
        if not _is_under_full_root(output_root):
            raise FullP0StepError(
                f"requested output root is outside {FULL_OUTPUT_ROOT}: {output_root}"
            )
        if declared_output_root is not None and _as_posix(output_root) != _as_posix(
            declared_output_root
        ):
            raise FullP0StepError(
                "requested output root does not match selected step output_root: "
                f"{output_root} != {declared_output_root}"
            )

    outputs = step.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise FullP0StepError("full-P0 step must declare output paths")
    for key, value in outputs.items():
        if not _is_under_full_root(str(value)):
            raise FullP0StepError(
                f"full-P0 output path for {key} is outside {FULL_OUTPUT_ROOT}: {value}"
            )

    validation = step.get("validation")
    if not isinstance(validation, dict):
        raise FullP0StepError("full-P0 step must declare a validation gate")
    if validation.get("paper_allowed") is not False:
        raise FullP0StepError("full-P0 step validation paper_allowed must be false")
    if validation.get("claim_allowed") is not False:
        raise FullP0StepError("full-P0 step validation claim_allowed must be false")
    if validation.get("review_status") != "not_reviewed":
        raise FullP0StepError("full-P0 step validation review_status must be not_reviewed")


def build_manifest_metadata(step: dict[str, Any]) -> dict[str, Any]:
    """Return the required metadata envelope for future produced manifests."""
    return {
        **REQUIRED_METADATA,
        "status": "not_run",
        "step_id": str(step.get("step_id", "")),
        "dataset": str(step.get("dataset", "")),
        "baseline": str(step.get("baseline", "")),
        "memory_policy": str(step.get("memory_policy", "")),
        "calibration": str(step.get("calibration", "")),
        "source_tier": "p0_full",
        "source_tier_role": "primary_full_output",
    }


def build_latest_run_metadata(step: dict[str, Any]) -> dict[str, Any]:
    """Return the required metadata envelope for future latest_run files."""
    return {
        **build_manifest_metadata(step),
        "run_scope": "p0_full_single_step",
    }


def _default_command_runner(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FullP0StepError(f"Expected JSON output was not created: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise FullP0StepError(f"JSON output must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _patch_json_metadata(path: Path, metadata: dict[str, Any]) -> None:
    payload = _read_json(path)
    payload.update(metadata)
    _write_json(path, payload)


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _run_id(stream_type: str, epsilon: str, seed: str) -> str:
    return (
        f"{mini_matrix.slug(stream_type)}_eps_{mini_matrix.slug(epsilon)}"
        f"_seed_{mini_matrix.slug(seed)}"
    )


def _category_run_id(category: str, stream_type: str, epsilon: str, seed: str) -> str:
    return f"{mini_matrix.slug(category)}_{_run_id(stream_type, epsilon, seed)}"


def _step_dataset_root(step: dict[str, Any]) -> str:
    dataset = str(step.get("dataset", ""))
    if dataset not in DEFAULT_DATASET_ROOTS:
        raise FullP0StepError(f"No default dataset_root for full-P0 dataset: {dataset}")
    return DEFAULT_DATASET_ROOTS[dataset]


def _step_runner_dataset_root(step: dict[str, Any]) -> str:
    dataset = str(step.get("dataset", ""))
    baseline = str(step.get("baseline", ""))
    if dataset == "VisA" and baseline in {"PatchCore", "RareCLIP"}:
        return "data/visa/1cls"
    return _step_dataset_root(step)


def _step_baseline_path(step: dict[str, Any]) -> str:
    baseline = str(step.get("baseline", ""))
    if baseline not in DEFAULT_BASELINE_PATHS:
        raise FullP0StepError(f"No default baseline_path for full-P0 baseline: {baseline}")
    return DEFAULT_BASELINE_PATHS[baseline]


def _validation_category(step: dict[str, Any], category: str | None) -> str:
    if category:
        return category
    dataset = str(step.get("dataset", ""))
    if dataset not in DEFAULT_VALIDATION_CATEGORIES:
        raise FullP0StepError(f"No default validation category for dataset: {dataset}")
    return DEFAULT_VALIDATION_CATEGORIES[dataset]


def _runner_memory_policy(step: dict[str, Any]) -> str:
    """Map full-P0 no-memory semantics onto existing wrapper contract values."""
    baseline = str(step.get("baseline", ""))
    memory_policy = str(step.get("memory_policy", "default/SCS"))
    if baseline in {"WinCLIP", "AnomalyCLIP"} and memory_policy == "default/no-memory":
        return "default/SCS"
    return memory_policy


def _run_command(command: list[str], *, command_runner: CommandRunner) -> None:
    return_code = command_runner(command)
    if return_code != 0:
        raise FullP0StepError(
            f"Command failed with exit code {return_code}: {' '.join(command)}"
        )


def _read_metric_row(path: Path, *, run_dir: Path) -> dict[str, str]:
    if not path.exists():
        raise FullP0StepError(f"Expected metrics output was not created: {path}")
    with path.open(newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if len(rows) != 1:
        raise FullP0StepError(f"Expected one metric row in {path}, got {len(rows)}")
    row = rows[0]
    row["run_dir"] = str(run_dir)
    row["status"] = "measured_full_p0"
    return row


def _run_categories(step: dict[str, Any], *, execution_mode: str, category: str | None) -> list[str]:
    if execution_mode == "lightweight":
        return [_validation_category(step, category)]
    categories = step.get("categories")
    if not isinstance(categories, list) or not categories:
        raise FullP0StepError("production full-P0 step must declare categories")
    return [str(value) for value in categories]


def _category_root_for_dataset(dataset_root: str | Path, dataset: str, category: str) -> Path:
    root = Path(dataset_root)
    if dataset == "VisA":
        one_class_root = root / "1cls" / category
        if one_class_root.is_dir():
            return one_class_root
    return root / category


def _write_aggregate_metrics(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise FullP0StepError("No full-P0 metric rows to aggregate")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _execute_lightweight_step(
    step: dict[str, Any],
    *,
    category: str | None,
    stream_length: int,
    command_runner: CommandRunner,
) -> None:
    output_root = Path(str(step["output_root"]))
    metadata = build_manifest_metadata(step)
    latest_run_metadata = build_latest_run_metadata(step)
    dataset = str(step["dataset"])
    baseline = str(step["baseline"])
    selected_category = _validation_category(step, category)
    rows: list[dict[str, str]] = []
    run_manifests: list[dict[str, Any]] = []
    latest_runs: list[dict[str, Any]] = []

    for stream_type in [str(value) for value in step.get("stream_types", [])]:
        for epsilon in [str(value) for value in step.get("contamination_epsilon", [])]:
            for seed in [str(value) for value in step.get("seeds", [])]:
                run_id = _run_id(stream_type, epsilon, seed)
                run_dir = output_root / "runs" / run_id
                config_path = output_root / "configs" / f"{run_id}.yaml"
                smoke_config = {
                    "baseline": baseline,
                    "baseline_path": _step_baseline_path(step),
                    "dataset": dataset,
                    "dataset_root": _step_dataset_root(step),
                    "category": selected_category,
                    "stream_type": stream_type,
                    "prevalence": 0.05,
                    "contamination_epsilon": float(epsilon),
                    "memory_policy": _runner_memory_policy(step),
                    "calibration": str(step.get("calibration", "none")),
                    "stream": {
                        "path": str(run_dir / "stream.json"),
                        "seed": int(seed),
                        "length": stream_length,
                        "burst_length": 5,
                    },
                    "outputs": {
                        "scores_csv": str(run_dir / "scores.csv"),
                        "latest_run": str(run_dir / "latest_run.json"),
                        "manifest": str(run_dir / "manifest.json"),
                    },
                    "provenance": {
                        "scoring_mode": "stream_ordered_full_p0_lightweight",
                        "latency_semantics": "wrapper_reported",
                        "training_source": "baseline_default",
                        "stream_source": "test/*",
                        "full_p0_memory_policy": str(step.get("memory_policy", "")),
                        "runner_memory_policy": _runner_memory_policy(step),
                    },
                }
                _write_yaml(config_path, smoke_config)

                _run_command(
                    ["bash", "scripts/run_smoke.sh", str(config_path)],
                    command_runner=command_runner,
                )
                _patch_json_metadata(run_dir / "latest_run.json", latest_run_metadata)
                _patch_json_metadata(run_dir / "manifest.json", metadata)

                _run_command(
                    [
                        "python3",
                        "experiments/evaluate.py",
                        "--scores-csv",
                        str(run_dir / "scores.csv"),
                        "--latest-run",
                        str(run_dir / "latest_run.json"),
                        "--output",
                        str(run_dir / "metrics.csv"),
                        "--manifest",
                        str(run_dir / "manifest.json"),
                    ],
                    command_runner=command_runner,
                )
                _patch_json_metadata(run_dir / "manifest.json", metadata)

                rows.append(_read_metric_row(run_dir / "metrics.csv", run_dir=run_dir))
                run_manifests.append(_read_json(run_dir / "manifest.json"))
                latest_runs.append(_read_json(run_dir / "latest_run.json"))

    expected = int(
        step.get("expected_lightweight_run_count")
        or step.get("expected_full_run_count")
        or 0
    )
    if len(rows) != expected:
        raise FullP0StepError(f"Full-P0 row count {len(rows)} != expected {expected}")

    outputs = step["outputs"]
    aggregate_metrics = Path(str(outputs["aggregate_metrics"]))
    aggregate_manifest = Path(str(outputs["aggregate_manifest"]))
    crd_lite_summary = Path(str(outputs["crd_lite_summary"]))

    crd_rows, crd_by_run_dir = mini_matrix.compute_crd_lite(
        rows,
        category=selected_category,
    )
    for row in rows:
        row["crd_lite"] = crd_by_run_dir.get(row.get("run_dir", ""), "NA")

    _write_aggregate_metrics(aggregate_metrics, rows)
    mini_matrix.write_crd_lite_summary(crd_lite_summary, crd_rows)
    manifest = {
        **metadata,
        "status": "measured_full_p0_lightweight_complete",
        "execution_mode": "lightweight",
        "validation_mode": "lightweight",
        "category": selected_category,
        "stream_length": stream_length,
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(rows),
        "expected_full_run_count": expected,
        "runs": rows,
        "latest_runs": latest_runs,
        "run_manifests": run_manifests,
        "notes": (
            "Lightweight single-category full-P0 validation step. "
            "Not a reviewed paper result."
        ),
    }
    _write_json(aggregate_manifest, manifest)


def _ensure_first_production_step(step: dict[str, Any]) -> None:
    step_id = str(step.get("step_id", ""))
    if step_id not in ALLOWED_PRODUCTION_STEP_IDS:
        raise FullP0StepError(
            "Production execution is currently enabled only for: "
            f"{', '.join(sorted(ALLOWED_PRODUCTION_STEP_IDS))}; selected {step_id}"
        )


def _execute_production_step(
    step: dict[str, Any],
    *,
    stream_length: int,
    command_runner: CommandRunner,
) -> None:
    _ensure_first_production_step(step)
    if command_runner is not _default_command_runner:
        _execute_production_step_with_commands(
            step,
            stream_length=stream_length,
            command_runner=command_runner,
        )
        return

    baseline = str(step.get("baseline", ""))
    if str(step.get("calibration", "")) == "temperature_scaling":
        _execute_temperature_materialized_step(step, stream_length=stream_length)
        return
    if baseline == "WinCLIP":
        _execute_winclip_production_step(step, stream_length=stream_length)
        return
    if baseline == "AnomalyCLIP":
        _execute_anomalyclip_production_step(step, stream_length=stream_length)
        return
    if baseline == "RareCLIP":
        _execute_rareclip_production_step(step, stream_length=stream_length)
        return
    if baseline in {"PatchCore", "RareCLIP"}:
        _execute_production_step_with_commands(
            step,
            stream_length=stream_length,
            command_runner=command_runner,
        )
        return
    raise FullP0StepError(f"Production execution is not implemented for {baseline}")


def _execute_production_step_with_commands(
    step: dict[str, Any],
    *,
    stream_length: int,
    command_runner: CommandRunner,
) -> None:
    output_root = Path(str(step["output_root"]))
    metadata = {
        **build_manifest_metadata(step),
        "execution_mode": "production",
    }
    latest_run_metadata = {
        **build_latest_run_metadata(step),
        "execution_mode": "production",
    }
    dataset = str(step["dataset"])
    dataset_root = _step_runner_dataset_root(step)
    baseline = str(step["baseline"])
    categories = _run_categories(step, execution_mode="production", category=None)
    rows: list[dict[str, str]] = []
    run_manifests: list[dict[str, Any]] = []
    latest_runs: list[dict[str, Any]] = []

    for selected_category in categories:
        for stream_type in [str(value) for value in step.get("stream_types", [])]:
            for epsilon in [str(value) for value in step.get("contamination_epsilon", [])]:
                for seed in [str(value) for value in step.get("seeds", [])]:
                    run_id = _category_run_id(selected_category, stream_type, epsilon, seed)
                    run_dir = output_root / "production_runs" / run_id
                    config_path = output_root / "production_configs" / f"{run_id}.yaml"
                    smoke_config = {
                        "baseline": baseline,
                        "baseline_path": _step_baseline_path(step),
                        "dataset": dataset,
                        "dataset_root": dataset_root,
                        "category": selected_category,
                        "stream_type": stream_type,
                        "prevalence": 0.05,
                        "contamination_epsilon": float(epsilon),
                        "memory_policy": _runner_memory_policy(step),
                        "calibration": str(step.get("calibration", "none")),
                        "stream": {
                            "path": str(run_dir / "stream.json"),
                            "seed": int(seed),
                            "length": stream_length,
                            "burst_length": 5,
                        },
                        "outputs": {
                            "scores_csv": str(run_dir / "scores.csv"),
                            "latest_run": str(run_dir / "latest_run.json"),
                            "manifest": str(run_dir / "manifest.json"),
                        },
                        "provenance": {
                            "scoring_mode": "stream_ordered_full_p0_production",
                            "latency_semantics": "wrapper_reported",
                            "training_source": "baseline_default",
                            "stream_source": "test/*",
                            "full_p0_memory_policy": str(step.get("memory_policy", "")),
                            "runner_memory_policy": _runner_memory_policy(step),
                        },
                    }
                    if baseline == "PatchCore":
                        smoke_config.update(
                            {
                                "sampler_percentage": PATCHCORE_PRODUCTION_VALIDATION_SAMPLER_PERCENTAGE,
                                "reservoir_memory_fraction": PATCHCORE_PRODUCTION_VALIDATION_SAMPLER_PERCENTAGE,
                                "model_cache_root": str(
                                    FULL_OUTPUT_ROOT / "patchcore_model_cache"
                                ),
                            }
                        )
                        smoke_config["provenance"].update(
                            {
                                "production_validation_sampler_percentage": (
                                    PATCHCORE_PRODUCTION_VALIDATION_SAMPLER_PERCENTAGE
                                ),
                                "model_cache_root": str(
                                    FULL_OUTPUT_ROOT / "patchcore_model_cache"
                                ),
                            }
                        )
                    _write_yaml(config_path, smoke_config)

                    _run_command(
                        ["bash", "scripts/run_smoke.sh", str(config_path)],
                        command_runner=command_runner,
                    )
                    _patch_json_metadata(run_dir / "latest_run.json", latest_run_metadata)
                    _patch_json_metadata(run_dir / "manifest.json", metadata)

                    _run_command(
                        [
                            "python3",
                            "experiments/evaluate.py",
                            "--scores-csv",
                            str(run_dir / "scores.csv"),
                            "--latest-run",
                            str(run_dir / "latest_run.json"),
                            "--output",
                            str(run_dir / "metrics.csv"),
                            "--manifest",
                            str(run_dir / "manifest.json"),
                        ],
                        command_runner=command_runner,
                    )
                    _patch_json_metadata(run_dir / "manifest.json", metadata)

                    row = _read_metric_row(run_dir / "metrics.csv", run_dir=run_dir)
                    row["category"] = selected_category
                    rows.append(row)
                    run_manifests.append(_read_json(run_dir / "manifest.json"))
                    latest_runs.append(_read_json(run_dir / "latest_run.json"))

    expected = int(step.get("expected_full_run_count") or 0)
    if len(rows) != expected:
        raise FullP0StepError(f"Full-P0 row count {len(rows)} != expected {expected}")

    outputs = step["outputs"]
    aggregate_metrics = Path(str(outputs["aggregate_metrics"]))
    aggregate_manifest = Path(str(outputs["aggregate_manifest"]))
    crd_lite_summary = Path(str(outputs["crd_lite_summary"]))

    crd_rows: list[dict[str, str]] = []
    crd_by_run_dir: dict[str, str] = {}
    for selected_category in categories:
        category_rows = [row for row in rows if row.get("category") == selected_category]
        category_crd_rows, category_crd_by_run_dir = mini_matrix.compute_crd_lite(
            category_rows,
            category=selected_category,
        )
        crd_rows.extend(category_crd_rows)
        crd_by_run_dir.update(category_crd_by_run_dir)
    for row in rows:
        row["crd_lite"] = crd_by_run_dir.get(row.get("run_dir", ""), "NA")

    _write_aggregate_metrics(aggregate_metrics, rows)
    mini_matrix.write_crd_lite_summary(crd_lite_summary, crd_rows)
    manifest = {
        **metadata,
        "status": "measured_full_p0_production_complete",
        "category_count": len(categories),
        "categories": categories,
        "stream_length": stream_length,
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(rows),
        "expected_full_run_count": expected,
        "runs": rows,
        "latest_runs": latest_runs,
        "run_manifests": run_manifests,
        "notes": (
            "Single production full-P0 validation step. "
            "Not a reviewed paper result."
        ),
    }
    if baseline == "PatchCore":
        manifest["production_validation_sampler_percentage"] = (
            PATCHCORE_PRODUCTION_VALIDATION_SAMPLER_PERCENTAGE
        )
        manifest["model_cache_root"] = str(FULL_OUTPUT_ROOT / "patchcore_model_cache")
    _write_json(aggregate_manifest, manifest)


def _execute_rareclip_production_step(step: dict[str, Any], *, stream_length: int) -> None:
    from experiments.baselines import rareclip

    output_root = _repo_path(str(step["output_root"]))
    metadata = {
        **build_manifest_metadata(step),
        "execution_mode": "production",
    }
    dataset = str(step["dataset"])
    dataset_root = _step_runner_dataset_root(step)
    dataset_root_path = rareclip._resolve_repo_path(dataset_root)
    categories = _run_categories(step, execution_mode="production", category=None)
    rows: list[dict[str, str]] = []
    run_manifests: list[dict[str, Any]] = []
    latest_runs: list[dict[str, Any]] = []
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    rareclip._ensure_rareclip_importable()
    try:
        import torch
        from rareclip import RareCLIP
        from rareclip_d import RareCLIP_d
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise rareclip._dependency_error(error) from error

    config = {
        "baseline": str(step["baseline"]),
        "dataset": dataset,
        "dataset_root": dataset_root,
        "memory_policy": _runner_memory_policy(step),
        "calibration": str(step.get("calibration", "none")),
        "scoring_mode": "stream_ordered_full_p0_production",
        "latency_semantics": "wrapper_reported",
    }
    memory_policy, _ = rareclip.validate_execution_contract(
        config,
        baseline_name="RareCLIP",
        supported_memory_policies={
            "default/SCS",
            "FIFO",
            "Reservoir",
            "Prototype-EMA",
        },
        supported_calibrations={"none", "temperature_scaling"},
    )
    checkpoint_path = rareclip._resolve_repo_path(
        str(rareclip._cfg(config, "checkpoint_path", rareclip.DEFAULT_CHECKPOINT))
    )
    if not checkpoint_path.is_file():
        raise FullP0StepError(f"RareCLIP checkpoint is required but missing: {checkpoint_path}")

    update_memory = rareclip._cfg(config, "online", True, bool)
    direct = rareclip._cfg(config, "direct", False, bool)
    args = rareclip._rareclip_args(config, checkpoint_path)
    fifo_memory_size = rareclip._cfg(config, "fifo_memory_size", args.keep_inum, int)
    reservoir_memory_size = rareclip._cfg(config, "reservoir_memory_size", args.keep_inum, int)
    reservoir_seed = rareclip._cfg(
        config,
        "reservoir_seed",
        rareclip._cfg(config, "seed", 0, int),
        int,
    )
    prototype_ema_memory_size = rareclip._cfg(
        config,
        "prototype_ema_memory_size",
        args.keep_inum,
        int,
    )
    prototype_ema_alpha = rareclip._cfg(config, "prototype_ema_alpha", 0.1, float)
    cache_dir = rareclip._resolve_repo_path(
        str(rareclip._cfg(config, "clip_cache_dir", rareclip.DEFAULT_CLIP_CACHE))
    )
    rareclip._prepare_openai_clip_cache(cache_dir)

    with rareclip._temporary_cwd(Path(rareclip.LOCAL_PATH).resolve()):
        model = RareCLIP_d(args) if direct else RareCLIP(args)
        if memory_policy == "FIFO":
            rareclip._install_fifo_sampler(model)
        elif memory_policy == "Reservoir":
            rareclip._install_reservoir_sampler(model, reservoir_seed)
        elif memory_policy == "Prototype-EMA":
            rareclip._install_prototype_ema_sampler(model, prototype_ema_alpha)
        if hasattr(model.clip_model, "eval"):
            model.clip_model.eval()

        for selected_category in categories:
            category_root = _category_root_for_dataset(
                dataset_root_path,
                dataset,
                selected_category,
            )
            if not category_root.is_dir():
                raise FullP0StepError(f"{dataset} category not found: {category_root}")
            for stream_type in [str(value) for value in step.get("stream_types", [])]:
                for epsilon in [str(value) for value in step.get("contamination_epsilon", [])]:
                    for seed in [str(value) for value in step.get("seeds", [])]:
                        model.renew_memory()
                        run_id = _category_run_id(
                            selected_category,
                            stream_type,
                            epsilon,
                            seed,
                        )
                        run_dir = output_root / "production_runs" / run_id
                        stream_path = run_dir / "stream.json"
                        scores_path = run_dir / "scores.csv"
                        latest_run_path = run_dir / "latest_run.json"
                        manifest_path = run_dir / "manifest.json"
                        metrics_path = run_dir / "metrics.csv"

                        stream_payload = make_streams.build_stream(
                            dataset_root=str(dataset_root_path),
                            dataset=dataset,
                            category=selected_category,
                            stream_type=stream_type,
                            prevalence=0.05,
                            contamination_epsilon=float(epsilon),
                            seed=int(seed),
                            length=stream_length,
                            burst_length=5,
                        )
                        stream_payload["metadata"].update(
                            {
                                "scoring_mode": "stream_ordered_full_p0_production",
                                "latency_semantics": "wrapper_reported",
                                "training_source": "baseline_default",
                                "stream_source": "test/*",
                            }
                        )
                        make_streams.write_stream(stream_payload, stream_path)
                        stream_items = rareclip._load_stream_items(str(stream_path))
                        score_rows = rareclip.RareCLIPWrapper._predict_rows(
                            model=model,
                            stream_items=stream_items,
                            dataset_root=dataset_root_path,
                            category=selected_category,
                            update_memory=update_memory,
                            device=model.device,
                            torch=torch,
                            memory_policy=memory_policy,
                            memory_limit=(
                                reservoir_memory_size
                                if memory_policy == "Reservoir"
                                else prototype_ema_memory_size
                                if memory_policy == "Prototype-EMA"
                                else fifo_memory_size
                            ),
                            memory_seed=reservoir_seed,
                            memory_alpha=prototype_ema_alpha,
                        )
                        _write_score_rows(scores_path, score_rows, rareclip.SCORE_FIELDS)

                        latest_run = _run_provenance(
                            step,
                            category=selected_category,
                            stream_type=stream_type,
                            epsilon=epsilon,
                            seed=seed,
                            stream_path=stream_path,
                            stream_payload=stream_payload,
                            scores_csv=scores_path,
                            timestamp=timestamp,
                        )
                        latest_run["memory_policy"] = str(step.get("memory_policy", ""))
                        _write_json(latest_run_path, latest_run)
                        _write_json(manifest_path, {**metadata, "status": "measured"})
                        evaluate.evaluate(
                            scores_path,
                            latest_run_path,
                            metrics_path,
                            manifest_path,
                        )
                        _patch_json_metadata(manifest_path, metadata)

                        row = _read_metric_row(metrics_path, run_dir=run_dir)
                        row["category"] = selected_category
                        rows.append(row)
                        run_manifests.append(_read_json(manifest_path))
                        latest_runs.append(_read_json(latest_run_path))

    expected = int(step.get("expected_full_run_count") or 0)
    if len(rows) != expected:
        raise FullP0StepError(f"Full-P0 row count {len(rows)} != expected {expected}")

    outputs = step["outputs"]
    aggregate_metrics = _repo_path(str(outputs["aggregate_metrics"]))
    aggregate_manifest = _repo_path(str(outputs["aggregate_manifest"]))
    crd_lite_summary = _repo_path(str(outputs["crd_lite_summary"]))

    crd_rows: list[dict[str, str]] = []
    crd_by_run_dir: dict[str, str] = {}
    for selected_category in categories:
        category_rows = [row for row in rows if row.get("category") == selected_category]
        category_crd_rows, category_crd_by_run_dir = mini_matrix.compute_crd_lite(
            category_rows,
            category=selected_category,
        )
        crd_rows.extend(category_crd_rows)
        crd_by_run_dir.update(category_crd_by_run_dir)
    for row in rows:
        row["crd_lite"] = crd_by_run_dir.get(row.get("run_dir", ""), "NA")

    _write_aggregate_metrics(aggregate_metrics, rows)
    mini_matrix.write_crd_lite_summary(crd_lite_summary, crd_rows)
    manifest = {
        **metadata,
        "status": "measured_full_p0_production_complete",
        "category_count": len(categories),
        "categories": categories,
        "stream_length": stream_length,
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(rows),
        "expected_full_run_count": expected,
        "runs": rows,
        "latest_runs": latest_runs,
        "run_manifests": run_manifests,
        "notes": (
            "Production full-P0 RareCLIP step with one model load per aggregate. "
            "Not a reviewed paper result."
        ),
    }
    _write_json(aggregate_manifest, manifest)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FullP0StepError(f"Expected CSV output was not created: {path}")
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _source_none_output_root(step: dict[str, Any]) -> Path:
    output_root = _repo_path(str(step["output_root"]))
    if output_root.name != "temperature_scaling":
        raise FullP0StepError(
            "temperature materialization requires a temperature_scaling output root"
        )
    return output_root.parent / "none"


def _require_source_none_manifest(source_manifest: dict[str, Any], step: dict[str, Any]) -> None:
    if source_manifest.get("execution_mode") != "production":
        raise FullP0StepError("source none manifest must be a production full-P0 output")
    if source_manifest.get("status") != "measured_full_p0_production_complete":
        raise FullP0StepError("source none manifest is not production-complete")
    if source_manifest.get("calibration") != "none":
        raise FullP0StepError("source manifest calibration must be none")
    if source_manifest.get("paper_allowed") is not False:
        raise FullP0StepError("source manifest paper_allowed must be false")
    if source_manifest.get("claim_allowed") is not False:
        raise FullP0StepError("source manifest claim_allowed must be false")
    if source_manifest.get("review_status") != "not_reviewed":
        raise FullP0StepError("source manifest review_status must be not_reviewed")
    for key in ["dataset", "baseline", "memory_policy"]:
        if source_manifest.get(key) != step.get(key):
            raise FullP0StepError(
                f"source manifest {key} {source_manifest.get(key)!r} "
                f"!= target {step.get(key)!r}"
            )


def _copy_stream_with_calibration_metadata(
    source_stream: Path,
    target_stream: Path,
    *,
    calibration: str,
) -> None:
    payload = _read_json(source_stream)
    metadata = payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise FullP0StepError(f"stream metadata must be an object: {source_stream}")
    metadata["calibration"] = calibration
    metadata["scoring_mode"] = "stream_ordered_full_p0_production"
    target_stream.parent.mkdir(parents=True, exist_ok=True)
    _write_json(target_stream, payload)


def _execute_temperature_materialized_step(
    step: dict[str, Any],
    *,
    stream_length: int,
) -> None:
    """Materialize full-P0 temperature rows from matching measured none scores.

    The project already treats temperature scaling as deterministic score
    postprocessing. This keeps full-P0 temperature steps paper-ineligible while
    avoiding a second baseline inference pass over the same streams.
    """
    output_root = _repo_path(str(step["output_root"]))
    source_root = _source_none_output_root(step)
    source_manifest_path = source_root / "manifest.json"
    source_manifest = _read_json(source_manifest_path)
    _require_source_none_manifest(source_manifest, step)

    source_runs = source_manifest.get("runs")
    if not isinstance(source_runs, list) or not source_runs:
        raise FullP0StepError(f"source manifest contains no runs: {source_manifest_path}")

    metadata = {
        **build_manifest_metadata(step),
        "execution_mode": "production",
    }
    latest_run_metadata = {
        **build_latest_run_metadata(step),
        "execution_mode": "production",
    }
    categories = [str(value) for value in source_manifest.get("categories", [])]
    if not categories:
        raise FullP0StepError("source manifest must record categories")

    rows: list[dict[str, str]] = []
    run_manifests: list[dict[str, Any]] = []
    latest_runs: list[dict[str, Any]] = []
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    source_stream_length = int(source_manifest.get("stream_length") or stream_length)

    for source_row in source_runs:
        source_run_dir = _repo_path(str(source_row.get("run_dir", "")))
        if not source_run_dir.is_dir():
            raise FullP0StepError(f"source run_dir is missing: {source_run_dir}")
        target_run_dir = output_root / "production_runs" / source_run_dir.name
        target_run_dir.mkdir(parents=True, exist_ok=True)

        source_scores = source_run_dir / "scores.csv"
        source_stream = source_run_dir / "stream.json"
        source_latest_run = source_run_dir / "latest_run.json"
        if not source_scores.exists() or not source_stream.exists() or not source_latest_run.exists():
            raise FullP0StepError(f"source run artifacts are incomplete: {source_run_dir}")

        scores_path = target_run_dir / "scores.csv"
        stream_path = target_run_dir / "stream.json"
        latest_run_path = target_run_dir / "latest_run.json"
        manifest_path = target_run_dir / "manifest.json"
        metrics_path = target_run_dir / "metrics.csv"

        shutil.copyfile(source_scores, scores_path)
        _copy_stream_with_calibration_metadata(
            source_stream,
            stream_path,
            calibration=str(step.get("calibration", "")),
        )
        calibration_metadata_path = scores_path.with_name(
            f"{scores_path.stem}_calibration.json"
        )
        calibration_metadata = apply_calibration_from_config(
            scores_path,
            {
                "calibration": str(step.get("calibration", "")),
                "calibration_temperature": 2.0,
            },
            metadata_output=calibration_metadata_path,
        )

        latest_run = _read_json(source_latest_run)
        latest_run.update(
            {
                **latest_run_metadata,
                "status": "measured",
                "category": str(source_row.get("category", latest_run.get("category", ""))),
                "stream_path": str(stream_path),
                "stream_type": str(source_row.get("stream_type", latest_run.get("stream_type", ""))),
                "contamination_epsilon": float(
                    source_row.get(
                        "contamination_epsilon",
                        latest_run.get("contamination_epsilon", 0.0),
                    )
                ),
                "stream_seed": latest_run.get("stream_seed"),
                "stream_length": source_stream_length,
                "scores_csv": str(scores_path),
                "timestamp": timestamp,
                "calibration": str(step.get("calibration", "")),
                "calibration_metadata": calibration_metadata,
                "command": "python3 experiments/run_p0_full_step.py",
                "notes": (
                    "Full-P0 temperature row materialized from matching measured "
                    "none-calibration full-P0 scores; not a reviewed paper result."
                ),
            }
        )
        _write_json(latest_run_path, latest_run)
        _write_json(manifest_path, {**metadata, "status": "measured"})
        evaluate.evaluate(scores_path, latest_run_path, metrics_path, manifest_path)
        _patch_json_metadata(manifest_path, metadata)

        row = _read_metric_row(metrics_path, run_dir=target_run_dir)
        row["category"] = str(source_row.get("category", ""))
        rows.append(row)
        run_manifests.append(_read_json(manifest_path))
        latest_runs.append(_read_json(latest_run_path))

    expected = int(step.get("expected_full_run_count") or 0)
    if len(rows) != expected:
        raise FullP0StepError(f"Full-P0 row count {len(rows)} != expected {expected}")

    outputs = step["outputs"]
    aggregate_metrics = _repo_path(str(outputs["aggregate_metrics"]))
    aggregate_manifest = _repo_path(str(outputs["aggregate_manifest"]))
    crd_lite_summary = _repo_path(str(outputs["crd_lite_summary"]))

    crd_rows: list[dict[str, str]] = []
    crd_by_run_dir: dict[str, str] = {}
    for selected_category in categories:
        category_rows = [row for row in rows if row.get("category") == selected_category]
        category_crd_rows, category_crd_by_run_dir = mini_matrix.compute_crd_lite(
            category_rows,
            category=selected_category,
        )
        crd_rows.extend(category_crd_rows)
        crd_by_run_dir.update(category_crd_by_run_dir)
    for row in rows:
        row["crd_lite"] = crd_by_run_dir.get(row.get("run_dir", ""), "NA")

    _write_aggregate_metrics(aggregate_metrics, rows)
    mini_matrix.write_crd_lite_summary(crd_lite_summary, crd_rows)
    manifest = {
        **metadata,
        "status": "measured_full_p0_production_complete",
        "category_count": len(categories),
        "categories": categories,
        "stream_length": source_stream_length,
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(rows),
        "expected_full_run_count": expected,
        "runs": rows,
        "latest_runs": latest_runs,
        "run_manifests": run_manifests,
        "source_none_manifest": str(source_manifest_path),
        "notes": (
            "Production full-P0 temperature step materialized from matching "
            "measured none-calibration full-P0 scores. Not a reviewed paper result."
        ),
    }
    _write_json(aggregate_manifest, manifest)


def _write_score_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _run_provenance(
    step: dict[str, Any],
    *,
    category: str,
    stream_type: str,
    epsilon: str,
    seed: str,
    stream_path: Path,
    stream_payload: dict[str, Any],
    scores_csv: Path,
    timestamp: str,
) -> dict[str, Any]:
    return {
        **build_latest_run_metadata(step),
        "execution_mode": "production",
        "status": "measured",
        "category": category,
        "stream_type": stream_type,
        "stream_path": str(stream_path),
        "prevalence": 0.05,
        "contamination_epsilon": float(epsilon),
        "stream_seed": int(seed),
        "stream_length": stream_payload.get("metadata", {}).get("applied_stream_length"),
        "scores_csv": str(scores_csv),
        "timestamp": timestamp,
        "stream_metadata": stream_payload.get("metadata", {}),
        "notes": "Single-step full-P0 production validation output; paper gate remains closed.",
    }


def _execute_winclip_production_step(step: dict[str, Any], *, stream_length: int) -> None:
    from experiments.baselines import winclip

    output_root = Path(str(step["output_root"]))
    metadata = {
        **build_manifest_metadata(step),
        "execution_mode": "production",
    }
    dataset_root = _step_dataset_root(step)
    dataset = str(step["dataset"])
    baseline = str(step["baseline"])
    categories = _run_categories(step, execution_mode="production", category=None)
    rows: list[dict[str, str]] = []
    run_manifests: list[dict[str, Any]] = []
    latest_runs: list[dict[str, Any]] = []
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    winclip._ensure_winclip_importable()
    try:
        import torch
        from WinCLIP import WinClipAD
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise winclip._dependency_error(error) from error

    config = {
        "baseline": baseline,
        "dataset": dataset,
        "dataset_root": dataset_root,
        "memory_policy": _runner_memory_policy(step),
        "calibration": str(step.get("calibration", "none")),
        "scoring_mode": "stream_ordered_full_p0_production",
        "latency_semantics": "wrapper_reported",
    }
    winclip.validate_execution_contract(
        config,
        baseline_name="WinCLIP",
        supported_calibrations={"none", "temperature_scaling"},
    )
    batch_size = winclip._cfg(config, "batch_size", 2, int)
    img_resize = winclip._cfg(config, "img_resize", 240, int)
    img_cropsize = winclip._cfg(config, "img_cropsize", 240, int)
    resolution = winclip._cfg(config, "resolution", 400, int)
    backbone = str(winclip._cfg(config, "backbone", "ViT-B-16-plus-240"))
    pretrained_dataset = str(winclip._cfg(config, "pretrained_dataset", "laion400m_e32"))
    scales = winclip._csv_ints(winclip._cfg(config, "scales", None), (2, 3))
    force_cpu = winclip._cfg(config, "use_cpu", not torch.cuda.is_available(), bool)
    device = torch.device("cpu" if force_cpu or not torch.cuda.is_available() else "cuda:0")

    model = WinClipAD(
        out_size_h=resolution,
        out_size_w=resolution,
        device=str(device),
        backbone=backbone,
        pretrained_dataset=pretrained_dataset,
        scales=scales,
        img_resize=img_resize,
        img_cropsize=img_cropsize,
    ).to(device)
    if device.type == "cpu":
        model.precision = "fp32"
        model.model.float()
    model.eval_mode()

    for selected_category in categories:
        category_root = _category_root_for_dataset(dataset_root, dataset, selected_category)
        if not category_root.is_dir():
            raise FullP0StepError(
                f"{dataset} category not found: {category_root}"
            )
        model.build_text_feature_gallery(selected_category)
        for stream_type in [str(value) for value in step.get("stream_types", [])]:
            for epsilon in [str(value) for value in step.get("contamination_epsilon", [])]:
                for seed in [str(value) for value in step.get("seeds", [])]:
                    run_id = _category_run_id(selected_category, stream_type, epsilon, seed)
                    run_dir = output_root / "production_runs" / run_id
                    stream_path = run_dir / "stream.json"
                    scores_path = run_dir / "scores.csv"
                    latest_run_path = run_dir / "latest_run.json"
                    manifest_path = run_dir / "manifest.json"
                    metrics_path = run_dir / "metrics.csv"

                    stream_payload = make_streams.build_stream(
                        dataset_root=dataset_root,
                        dataset=dataset,
                        category=selected_category,
                        stream_type=stream_type,
                        prevalence=0.05,
                        contamination_epsilon=float(epsilon),
                        seed=int(seed),
                        length=stream_length,
                        burst_length=5,
                    )
                    stream_payload["metadata"].update(
                        {
                            "scoring_mode": "stream_ordered_full_p0_production",
                            "latency_semantics": "wrapper_reported",
                            "training_source": "baseline_default",
                            "stream_source": "test/*",
                        }
                    )
                    make_streams.write_stream(stream_payload, stream_path)
                    stream_items = winclip._load_stream_items(str(stream_path))
                    score_rows = winclip.WinCLIPWrapper._predict_rows(
                        model=model,
                        stream_items=stream_items,
                        dataset_root=dataset_root,
                        category=selected_category,
                        batch_size=batch_size,
                        device=device,
                        torch=torch,
                    )
                    _write_score_rows(scores_path, score_rows, winclip.SCORE_FIELDS)

                    latest_run = _run_provenance(
                        step,
                        category=selected_category,
                        stream_type=stream_type,
                        epsilon=epsilon,
                        seed=seed,
                        stream_path=stream_path,
                        stream_payload=stream_payload,
                        scores_csv=scores_path,
                        timestamp=timestamp,
                    )
                    latest_run["memory_policy"] = str(step.get("memory_policy", ""))
                    _write_json(latest_run_path, latest_run)
                    _write_json(manifest_path, {**metadata, "status": "measured"})
                    evaluate.evaluate(scores_path, latest_run_path, metrics_path, manifest_path)
                    _patch_json_metadata(manifest_path, metadata)

                    row = _read_metric_row(metrics_path, run_dir=run_dir)
                    row["category"] = selected_category
                    rows.append(row)
                    run_manifests.append(_read_json(manifest_path))
                    latest_runs.append(_read_json(latest_run_path))

    expected = int(step.get("expected_full_run_count") or 0)
    if len(rows) != expected:
        raise FullP0StepError(f"Full-P0 row count {len(rows)} != expected {expected}")

    outputs = step["outputs"]
    aggregate_metrics = Path(str(outputs["aggregate_metrics"]))
    aggregate_manifest = Path(str(outputs["aggregate_manifest"]))
    crd_lite_summary = Path(str(outputs["crd_lite_summary"]))

    crd_rows: list[dict[str, str]] = []
    crd_by_run_dir: dict[str, str] = {}
    for selected_category in categories:
        category_rows = [row for row in rows if row.get("category") == selected_category]
        category_crd_rows, category_crd_by_run_dir = mini_matrix.compute_crd_lite(
            category_rows,
            category=selected_category,
        )
        crd_rows.extend(category_crd_rows)
        crd_by_run_dir.update(category_crd_by_run_dir)
    for row in rows:
        row["crd_lite"] = crd_by_run_dir.get(row.get("run_dir", ""), "NA")

    _write_aggregate_metrics(aggregate_metrics, rows)
    mini_matrix.write_crd_lite_summary(crd_lite_summary, crd_rows)
    manifest = {
        **metadata,
        "status": "measured_full_p0_production_complete",
        "category_count": len(categories),
        "categories": categories,
        "stream_length": stream_length,
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(rows),
        "expected_full_run_count": expected,
        "runs": rows,
        "latest_runs": latest_runs,
        "run_manifests": run_manifests,
        "notes": (
            "Single production full-P0 validation step. "
            "Not a reviewed paper result."
        ),
    }
    _write_json(aggregate_manifest, manifest)


def _execute_anomalyclip_production_step(
    step: dict[str, Any],
    *,
    stream_length: int,
) -> None:
    from experiments.baselines import anomalyclip

    output_root = _repo_path(str(step["output_root"]))
    metadata = {
        **build_manifest_metadata(step),
        "execution_mode": "production",
    }
    dataset_root = _step_dataset_root(step)
    dataset_root_path = anomalyclip._resolve_repo_path(dataset_root)
    dataset = str(step["dataset"])
    baseline = str(step["baseline"])
    categories = _run_categories(step, execution_mode="production", category=None)
    rows: list[dict[str, str]] = []
    run_manifests: list[dict[str, Any]] = []
    latest_runs: list[dict[str, Any]] = []
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    anomalyclip._ensure_anomalyclip_importable()
    try:
        import torch
        from scipy.ndimage import gaussian_filter

        import AnomalyCLIP_lib
        from prompt_ensemble import AnomalyCLIP_PromptLearner
        from utils import get_transform
    except ImportError as error:  # pragma: no cover - environment-dependent
        raise anomalyclip._dependency_error(error) from error

    config = {
        "baseline": baseline,
        "dataset": dataset,
        "dataset_root": dataset_root,
        "memory_policy": _runner_memory_policy(step),
        "calibration": str(step.get("calibration", "none")),
        "scoring_mode": "stream_ordered_full_p0_production",
        "latency_semantics": "wrapper_reported",
    }
    anomalyclip.validate_execution_contract(
        config,
        baseline_name="AnomalyCLIP",
        supported_calibrations={"none", "temperature_scaling"},
    )
    checkpoint_path = anomalyclip._resolve_repo_path(
        str(anomalyclip._cfg(config, "checkpoint_path", anomalyclip.DEFAULT_CHECKPOINT))
    )
    if not checkpoint_path.is_file():
        raise FullP0StepError(f"AnomalyCLIP checkpoint is required but missing: {checkpoint_path}")

    image_size = anomalyclip._cfg(config, "image_size", 518, int)
    depth = anomalyclip._cfg(config, "depth", 9, int)
    n_ctx = anomalyclip._cfg(config, "n_ctx", 12, int)
    t_n_ctx = anomalyclip._cfg(config, "t_n_ctx", 4, int)
    features_list = anomalyclip._csv_ints(
        anomalyclip._cfg(config, "features_list", None),
        (6, 12, 18, 24),
    )
    feature_map_layer = anomalyclip._csv_ints(
        anomalyclip._cfg(config, "feature_map_layer", None),
        (0, 1, 2, 3),
    )
    sigma = anomalyclip._cfg(config, "sigma", 4, int)
    dpam_layer = anomalyclip._cfg(config, "dpam_layer", 20, int)
    score_source = str(anomalyclip._cfg(config, "score_source", "text_prob"))
    clip_model_name = str(
        anomalyclip._cfg(config, "clip_model_name", "ViT-L/14@336px")
    )
    clip_cache = anomalyclip._resolve_repo_path(
        str(anomalyclip._cfg(config, "clip_download_root", anomalyclip.DEFAULT_CLIP_CACHE))
    )
    force_cpu = anomalyclip._cfg(config, "use_cpu", not torch.cuda.is_available(), bool)
    device = torch.device("cpu" if force_cpu or not torch.cuda.is_available() else "cuda:0")

    clip_cache.mkdir(parents=True, exist_ok=True)
    parameters = {
        "Prompt_length": n_ctx,
        "learnabel_text_embedding_depth": depth,
        "learnabel_text_embedding_length": t_n_ctx,
    }
    args = SimpleNamespace(image_size=image_size)

    with anomalyclip._temporary_cwd(Path(anomalyclip.LOCAL_PATH).resolve()):
        model, _ = AnomalyCLIP_lib.load(
            clip_model_name,
            device=str(device),
            design_details=parameters,
            download_root=str(clip_cache),
        )
        model.eval()
        preprocess, _ = get_transform(args)
        prompt_learner = AnomalyCLIP_PromptLearner(model.to("cpu"), parameters)
        checkpoint = torch.load(str(checkpoint_path), map_location="cpu")
        prompt_learner.load_state_dict(checkpoint["prompt_learner"])
        prompt_learner.to(device)
        model.to(device)
        model.visual.DAPM_replace(DPAM_layer=dpam_layer)

        prompts, tokenized_prompts, compound_prompts_text = prompt_learner(cls_id=None)
        text_features = model.encode_text_learn(
            prompts,
            tokenized_prompts,
            compound_prompts_text,
        ).float()
        text_features = torch.stack(torch.chunk(text_features, dim=0, chunks=2), dim=1)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        for selected_category in categories:
            category_root = _category_root_for_dataset(
                dataset_root_path,
                dataset,
                selected_category,
            )
            if not category_root.is_dir():
                raise FullP0StepError(f"{dataset} category not found: {category_root}")
            for stream_type in [str(value) for value in step.get("stream_types", [])]:
                for epsilon in [str(value) for value in step.get("contamination_epsilon", [])]:
                    for seed in [str(value) for value in step.get("seeds", [])]:
                        run_id = _category_run_id(
                            selected_category,
                            stream_type,
                            epsilon,
                            seed,
                        )
                        run_dir = output_root / "production_runs" / run_id
                        stream_path = run_dir / "stream.json"
                        scores_path = run_dir / "scores.csv"
                        latest_run_path = run_dir / "latest_run.json"
                        manifest_path = run_dir / "manifest.json"
                        metrics_path = run_dir / "metrics.csv"

                        stream_payload = make_streams.build_stream(
                            dataset_root=str(dataset_root_path),
                            dataset=dataset,
                            category=selected_category,
                            stream_type=stream_type,
                            prevalence=0.05,
                            contamination_epsilon=float(epsilon),
                            seed=int(seed),
                            length=stream_length,
                            burst_length=5,
                        )
                        stream_payload["metadata"].update(
                            {
                                "scoring_mode": "stream_ordered_full_p0_production",
                                "latency_semantics": "wrapper_reported",
                                "training_source": "baseline_default",
                                "stream_source": "test/*",
                            }
                        )
                        make_streams.write_stream(stream_payload, stream_path)
                        stream_items = anomalyclip._load_stream_items(str(stream_path))
                        score_rows = anomalyclip.AnomalyCLIPWrapper._predict_rows(
                            model=model,
                            preprocess=preprocess,
                            text_features=text_features,
                            stream_items=stream_items,
                            dataset_root=dataset_root_path,
                            category=selected_category,
                            image_size=image_size,
                            features_list=features_list,
                            feature_map_start=int(feature_map_layer[0]),
                            sigma=sigma,
                            dpam_layer=dpam_layer,
                            score_source=score_source,
                            device=device,
                            torch=torch,
                            anomalyclip_lib=AnomalyCLIP_lib,
                            gaussian_filter=gaussian_filter,
                        )
                        _write_score_rows(
                            scores_path,
                            score_rows,
                            anomalyclip.SCORE_FIELDS,
                        )

                        latest_run = _run_provenance(
                            step,
                            category=selected_category,
                            stream_type=stream_type,
                            epsilon=epsilon,
                            seed=seed,
                            stream_path=stream_path,
                            stream_payload=stream_payload,
                            scores_csv=scores_path,
                            timestamp=timestamp,
                        )
                        latest_run["memory_policy"] = str(step.get("memory_policy", ""))
                        _write_json(latest_run_path, latest_run)
                        _write_json(manifest_path, {**metadata, "status": "measured"})
                        evaluate.evaluate(
                            scores_path,
                            latest_run_path,
                            metrics_path,
                            manifest_path,
                        )
                        _patch_json_metadata(manifest_path, metadata)

                        row = _read_metric_row(metrics_path, run_dir=run_dir)
                        row["category"] = selected_category
                        rows.append(row)
                        run_manifests.append(_read_json(manifest_path))
                        latest_runs.append(_read_json(latest_run_path))

    expected = int(step.get("expected_full_run_count") or 0)
    if len(rows) != expected:
        raise FullP0StepError(f"Full-P0 row count {len(rows)} != expected {expected}")

    outputs = step["outputs"]
    aggregate_metrics = _repo_path(str(outputs["aggregate_metrics"]))
    aggregate_manifest = _repo_path(str(outputs["aggregate_manifest"]))
    crd_lite_summary = _repo_path(str(outputs["crd_lite_summary"]))

    crd_rows: list[dict[str, str]] = []
    crd_by_run_dir: dict[str, str] = {}
    for selected_category in categories:
        category_rows = [row for row in rows if row.get("category") == selected_category]
        category_crd_rows, category_crd_by_run_dir = mini_matrix.compute_crd_lite(
            category_rows,
            category=selected_category,
        )
        crd_rows.extend(category_crd_rows)
        crd_by_run_dir.update(category_crd_by_run_dir)
    for row in rows:
        row["crd_lite"] = crd_by_run_dir.get(row.get("run_dir", ""), "NA")

    _write_aggregate_metrics(aggregate_metrics, rows)
    mini_matrix.write_crd_lite_summary(crd_lite_summary, crd_rows)
    manifest = {
        **metadata,
        "status": "measured_full_p0_production_complete",
        "category_count": len(categories),
        "categories": categories,
        "stream_length": stream_length,
        "aggregate_metrics": str(aggregate_metrics),
        "crd_lite_summary": str(crd_lite_summary),
        "run_count": len(rows),
        "expected_full_run_count": expected,
        "runs": rows,
        "latest_runs": latest_runs,
        "run_manifests": run_manifests,
        "notes": (
            "Single production full-P0 validation step. "
            "Not a reviewed paper result."
        ),
    }
    _write_json(aggregate_manifest, manifest)


def run_step(
    plan: dict[str, Any],
    *,
    selector: str,
    output_root: Path | None = None,
    dry_run: bool = False,
    validation_mode: str | None = None,
    category: str | None = None,
    stream_length: int = 20,
    command_runner: CommandRunner = _default_command_runner,
) -> tuple[int, dict[str, Any]]:
    index, step = resolve_step(plan, selector)
    validate_step_contract(step, output_root=output_root)
    step_id = str(step.get("step_id", index))

    if dry_run:
        print(
            f"[{index}] DRY-RUN full-P0 step {step_id}: "
            f"output_root={step.get('output_root')}"
        )
        return index, step

    if validation_mode == "lightweight":
        _execute_lightweight_step(
            step,
            category=category,
            stream_length=stream_length,
            command_runner=command_runner,
        )
        print(f"[{index}] COMPLETE full-P0 step {step_id}: validation_mode=lightweight")
        return index, step

    _execute_production_step(
        step,
        stream_length=stream_length,
        command_runner=command_runner,
    )
    print(f"[{index}] COMPLETE full-P0 step {step_id}: execution_mode=production")
    return index, step


def verify_completed_step(step: dict[str, Any], *, completion_mode: str = "production") -> None:
    validate_step_contract(step)
    outputs = step["outputs"]
    metrics_path = Path(str(outputs["aggregate_metrics"]))
    manifest_path = Path(str(outputs["aggregate_manifest"]))
    crd_path = Path(str(outputs["crd_lite_summary"]))
    for path in [metrics_path, manifest_path, crd_path]:
        if not path.exists():
            raise FullP0StepError(f"Expected full-P0 output missing: {path}")
    with metrics_path.open(newline="") as handle:
        row_count = sum(1 for _ in csv.DictReader(handle))
    expected_field = (
        "expected_lightweight_run_count"
        if completion_mode == "lightweight"
        else "expected_full_run_count"
    )
    expected = int(step.get(expected_field) or 0)
    if row_count != expected:
        raise FullP0StepError(f"Full-P0 metrics row count {row_count} != expected {expected}")
    manifest = _read_json(manifest_path)
    _enforce_metadata(manifest, context="aggregate manifest")
    if manifest.get("execution_mode") != completion_mode:
        raise FullP0StepError(
            f"aggregate manifest execution_mode must be {completion_mode!r}"
        )
    if completion_mode == "production":
        expected_category_count = step.get("category_count")
        if manifest.get("category_count") != expected_category_count:
            raise FullP0StepError(
                "aggregate manifest category_count "
                f"{manifest.get('category_count')!r} != expected "
                f"{expected_category_count!r}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--step", help="Full-P0 step id or zero-based index")
    selector.add_argument("--step-id", help="Full-P0 step id")
    selector.add_argument("--index", type=int, help="Zero-based full-P0 step index")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--validation-mode",
        choices=["lightweight"],
        help="Run a bounded single-category validation step instead of production full P0.",
    )
    parser.add_argument("--category", help="Override lightweight validation category")
    parser.add_argument("--stream-length", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selector = args.step
    if selector is None and args.step_id is not None:
        selector = args.step_id
    if selector is None and args.index is not None:
        selector = str(args.index)
    assert selector is not None

    try:
        plan = load_plan(args.plan)
        index, step = run_step(
            plan,
            selector=selector,
            output_root=args.output_root,
            dry_run=args.dry_run,
            validation_mode=args.validation_mode,
            category=args.category,
            stream_length=args.stream_length,
        )
        if not args.dry_run:
            verify_completed_step(
                step,
                completion_mode=(
                    "lightweight" if args.validation_mode == "lightweight" else "production"
                ),
            )
    except (json.JSONDecodeError, OSError, FullP0StepError) as error:
        raise SystemExit(f"ERROR: {error}") from error

    print(
        "selected_step="
        f"{index} step_id={step.get('step_id')} run_tier=p0_full "
        "paper_allowed=false claim_allowed=false review_status=not_reviewed"
    )


if __name__ == "__main__":
    main()
