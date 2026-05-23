#!/usr/bin/env python3
"""Build a paper-ineligible P0 shard plan from the canonical P0 config.

The shard plan is an orchestration artifact, not a metric artifact. It maps the
intended P0 matrix onto the currently implemented dataset/baseline stream
matrix runners and records unsupported dimensions explicitly instead of
silently dropping them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/p0_shards.py ...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for P0 shard config parsing") from error

from experiments import category_sweep, mini_matrix

DEFAULT_OUTPUT = Path("results/latest/p0_shards/manifest.json")
CONFIG_ROOT = Path("experiments/configs")
SCRIPT_ROOT = Path("scripts")
DATASET_PREFIX = {
    "MVTec AD": "mvtec",
    "VisA": "visa",
}


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


def _dataset_prefix(dataset: str) -> str:
    if dataset not in DATASET_PREFIX:
        raise SystemExit(f"Unsupported P0 dataset for shard planning: {dataset}")
    return DATASET_PREFIX[dataset]


def _shard_config_path(dataset: str, baseline: str) -> Path:
    return (
        CONFIG_ROOT
        / f"{_dataset_prefix(dataset)}_full_category_stream_matrix_{mini_matrix.slug(baseline)}.yaml"
    )


def _shard_runner_path(dataset: str, baseline: str) -> Path:
    return (
        SCRIPT_ROOT
        / f"run_{_dataset_prefix(dataset)}_full_category_stream_matrix_{mini_matrix.slug(baseline)}.sh"
    )


def _calibration_shard_config_path(dataset: str, baseline: str) -> Path:
    return (
        CONFIG_ROOT
        / (
            f"{_dataset_prefix(dataset)}_full_category_stream_matrix_"
            f"{mini_matrix.slug(baseline)}_temperature.yaml"
        )
    )


def _calibration_shard_runner_path(dataset: str, baseline: str) -> Path:
    return (
        SCRIPT_ROOT
        / (
            f"run_{_dataset_prefix(dataset)}_full_category_stream_matrix_"
            f"{mini_matrix.slug(baseline)}_temperature.sh"
        )
    )


def _memory_policy_slug(memory_policy: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", memory_policy.strip().lower()).strip("_")


def _memory_shard_config_path(dataset: str, baseline: str, memory_policy: str) -> Path:
    return (
        CONFIG_ROOT
        / (
            f"{_dataset_prefix(dataset)}_full_category_stream_matrix_"
            f"{mini_matrix.slug(baseline)}_{_memory_policy_slug(memory_policy)}.yaml"
        )
    )


def _memory_shard_runner_path(dataset: str, baseline: str, memory_policy: str) -> Path:
    return (
        SCRIPT_ROOT
        / (
            f"run_{_dataset_prefix(dataset)}_full_category_stream_matrix_"
            f"{mini_matrix.slug(baseline)}_{_memory_policy_slug(memory_policy)}.sh"
        )
    )


def _supported_memory_policies(
    baseline: str, p0_cfg: dict[str, Any]
) -> tuple[list[str], list[str]]:
    intended = [str(value) for value in _as_list(p0_cfg.get("memory_policies"), [])]
    scoped = {str(value) for value in _as_list(p0_cfg.get("memory_policy_scope"), [])}
    if baseline not in scoped:
        return ["default/SCS"], []
    implemented_by_baseline = {
        "RareCLIP": {"default/SCS", "FIFO", "Reservoir", "Prototype-EMA"},
        "PatchCore": {"default/SCS", "FIFO", "Reservoir", "Prototype-EMA"},
    }
    implemented = implemented_by_baseline.get(baseline, {"default/SCS"})
    supported = [value for value in intended if value in implemented]
    unsupported = [value for value in intended if value not in supported]
    return supported, unsupported


def _implemented_memory_policies(
    baseline: str, shard_cfg: dict[str, Any] | None, p0_cfg: dict[str, Any]
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    supported, _ = _supported_memory_policies(baseline, p0_cfg)
    if not supported:
        return [], [], []
    current = "default/SCS"
    if shard_cfg is not None:
        current = str(shard_cfg.get("memory_policy", "default/SCS"))
    implemented = [value for value in supported if value == current]
    memory_shards: list[dict[str, Any]] = []
    for memory_policy in supported:
        if memory_policy == current:
            continue
        memory_shard = _memory_shard(
            str(shard_cfg.get("dataset", "")) if shard_cfg else "",
            baseline,
            memory_policy,
        )
        memory_shards.append(memory_shard)
        if memory_shard["status"] == "ready_smoke_shard":
            implemented.append(memory_policy)
    missing = [value for value in supported if value not in implemented]
    return implemented, missing, memory_shards


def _memory_shard(dataset: str, baseline: str, memory_policy: str) -> dict[str, Any]:
    config_path = _memory_shard_config_path(dataset, baseline, memory_policy)
    runner_path = _memory_shard_runner_path(dataset, baseline, memory_policy)
    shard_cfg = _read_shard_config(config_path)
    status = (
        "ready_smoke_shard"
        if config_path.exists() and runner_path.exists()
        else "missing_runner_or_config"
    )
    return {
        "memory_policy": memory_policy,
        "paper_allowed": False,
        "status": status,
        "config": str(config_path),
        "runner": str(runner_path),
        "command": f"bash {runner_path}",
        "current_smoke_run_count": _expected_smoke_runs(shard_cfg),
        "outputs": _output_paths(shard_cfg),
        "notes": (
            "Memory-policy shard is a measured smoke shard and remains "
            "paper-ineligible."
        ),
    }


def _supported_calibration(p0_cfg: dict[str, Any]) -> tuple[list[str], list[str]]:
    intended = [str(value) for value in _as_list(p0_cfg.get("calibration"), [])]
    implemented = {"none", "temperature_scaling"}
    supported = [value for value in intended if value in implemented]
    unsupported = [value for value in intended if value not in supported]
    return supported, unsupported


def _read_shard_config(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_config(path)


def _output_paths(shard_cfg: dict[str, Any] | None) -> dict[str, str]:
    if shard_cfg is None:
        return {}
    metrics, manifest, crd = category_sweep.default_output_paths(shard_cfg)
    return {
        "aggregate_metrics": str(metrics),
        "aggregate_manifest": str(manifest),
        "crd_lite_summary": str(crd),
    }


def _expected_smoke_runs(shard_cfg: dict[str, Any] | None) -> int:
    if shard_cfg is None:
        return 0
    categories = _as_list(shard_cfg.get("categories", shard_cfg.get("category")), [])
    baselines = shard_cfg.get("baselines") or [shard_cfg.get("baseline")]
    stream_types = _as_list(shard_cfg.get("stream_types", shard_cfg.get("stream_type")), [])
    epsilons = _as_list(shard_cfg.get("contamination_epsilon"), [])
    calibrations = _as_list(shard_cfg.get("calibration"), ["none"])
    return (
        len(categories)
        * len(baselines)
        * len(stream_types)
        * len(epsilons)
        * len(calibrations)
    )


def _calibration_shard(dataset: str, baseline: str) -> dict[str, Any]:
    config_path = _calibration_shard_config_path(dataset, baseline)
    runner_path = _calibration_shard_runner_path(dataset, baseline)
    shard_cfg = _read_shard_config(config_path)
    status = (
        "ready_smoke_shard"
        if config_path.exists() and runner_path.exists()
        else "missing_runner_or_config"
    )
    shard: dict[str, Any] = {
        "calibration": "temperature_scaling",
        "paper_allowed": False,
        "status": status,
        "config": str(config_path),
        "runner": str(runner_path),
        "command": f"bash {runner_path}",
        "current_smoke_run_count": _expected_smoke_runs(shard_cfg),
        "outputs": _output_paths(shard_cfg),
        "notes": (
            "Temperature scaling shard is materialized from measured smoke "
            "scores and remains paper-ineligible."
        ),
    }
    return shard


def build_shards(p0_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    supported_calibration, unsupported_calibration = _supported_calibration(p0_cfg)
    shards: list[dict[str, Any]] = []
    for dataset in [str(value) for value in _as_list(p0_cfg.get("datasets"), [])]:
        for baseline in [str(value) for value in _as_list(p0_cfg.get("baselines"), [])]:
            config_path = _shard_config_path(dataset, baseline)
            runner_path = _shard_runner_path(dataset, baseline)
            shard_cfg = _read_shard_config(config_path)
            calibration_shard = _calibration_shard(dataset, baseline)
            supported_memory, unsupported_memory = _supported_memory_policies(
                baseline, p0_cfg
            )
            implemented_memory, missing_memory, memory_shards = _implemented_memory_policies(
                baseline, shard_cfg, p0_cfg
            )
            implemented_calibration = ["none"]
            missing_calibration = []
            if "temperature_scaling" in supported_calibration:
                if calibration_shard["status"] == "ready_smoke_shard":
                    implemented_calibration.append("temperature_scaling")
                else:
                    missing_calibration.append("temperature_scaling")
            shard_id = (
                f"{mini_matrix.slug(dataset)}_{mini_matrix.slug(baseline)}"
                "_stream_epsilon_smoke"
            )
            shard = {
                "shard_id": shard_id,
                "paper_allowed": False,
                "status": (
                    "ready_smoke_shard"
                    if config_path.exists() and runner_path.exists()
                    else "missing_runner_or_config"
                ),
                "dataset": dataset,
                "baseline": baseline,
                "config": str(config_path),
                "runner": str(runner_path),
                "command": f"bash {runner_path}",
                "current_supported_memory_policies": supported_memory,
                "unsupported_memory_policies": unsupported_memory,
                "current_implemented_memory_policies": implemented_memory,
                "missing_memory_policies": missing_memory,
                "memory_policy_shards": memory_shards,
                "current_supported_calibration": supported_calibration,
                "unsupported_calibration": unsupported_calibration,
                "current_implemented_calibration": implemented_calibration,
                "missing_calibration": missing_calibration,
                "intended_stream_types": [
                    str(value) for value in _as_list(p0_cfg.get("stream_types"), [])
                ],
                "intended_contamination_epsilon": [
                    str(value)
                    for value in _as_list(p0_cfg.get("contamination_epsilon"), [])
                ],
                "current_smoke_run_count": _expected_smoke_runs(shard_cfg),
                "outputs": _output_paths(shard_cfg),
                "calibration_shards": [calibration_shard],
                "notes": (
                    "Current shard maps to the implemented all-category stream/epsilon "
                    "smoke runner. Calibration shards are tracked separately and are "
                    "not reviewed full-P0 shards."
                ),
            }
            shards.append(shard)
    return shards


def build_manifest(p0_config: Path) -> dict[str, Any]:
    p0_cfg = _load_config(p0_config)
    shards = build_shards(p0_cfg)
    missing = [
        shard["shard_id"]
        for shard in shards
        if shard["status"] != "ready_smoke_shard"
    ]
    unsupported_memory = sorted(
        {
            value
            for shard in shards
            for value in shard["unsupported_memory_policies"]
        }
    )
    unsupported_calibration = sorted(
        {
            value
            for shard in shards
            for value in shard["unsupported_calibration"]
        }
    )
    missing_memory = [
        f"{shard['shard_id']}:{value}"
        for shard in shards
        for value in shard.get("missing_memory_policies", [])
    ]
    ready_memory_shards = [
        memory_shard
        for shard in shards
        for memory_shard in shard.get("memory_policy_shards", [])
        if memory_shard.get("status") == "ready_smoke_shard"
    ]
    missing_calibration = [
        f"{shard['shard_id']}:{value}"
        for shard in shards
        for value in shard.get("missing_calibration", [])
    ]
    ready_calibration_shards = [
        calibration_shard
        for shard in shards
        for calibration_shard in shard.get("calibration_shards", [])
        if calibration_shard.get("status") == "ready_smoke_shard"
    ]
    if missing:
        status = "p0_shard_plan_incomplete"
    elif missing_memory:
        status = "p0_shard_plan_ready_memory_partial"
    elif missing_calibration:
        status = "p0_shard_plan_ready_calibration_partial"
    else:
        status = "p0_shard_plan_ready"
    return {
        "status": status,
        "paper_allowed": False,
        "p0_config": str(p0_config),
        "shard_count": len(shards),
        "ready_shard_count": len(shards) - len(missing),
        "ready_memory_policy_shard_count": len(ready_memory_shards),
        "ready_calibration_shard_count": len(ready_calibration_shards),
        "missing_memory_policy_shards": missing_memory,
        "missing_calibration_shards": missing_calibration,
        "missing_shards": missing,
        "unsupported_memory_policies": unsupported_memory,
        "unsupported_calibration": unsupported_calibration,
        "shards": shards,
        "notes": (
            "P0 orchestration plan only. It does not create metrics and must not be "
            "used as paper evidence."
        ),
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def verify_manifest(manifest: dict[str, Any], *, require_outputs: bool) -> list[str]:
    errors: list[str] = []
    if manifest.get("paper_allowed") is not False:
        errors.append("manifest paper_allowed must be false")
    for shard in manifest.get("shards", []):
        if shard.get("paper_allowed") is not False:
            errors.append(f"{shard.get('shard_id')}: paper_allowed must be false")
        for key in ["config", "runner"]:
            path = Path(str(shard.get(key, "")))
            if not path.exists():
                errors.append(f"{shard.get('shard_id')}: missing {key}: {path}")
        if require_outputs:
            for key, value in (shard.get("outputs") or {}).items():
                if not Path(str(value)).exists():
                    errors.append(
                        f"{shard.get('shard_id')}: missing output {key}: {value}"
                    )
        for memory_shard in shard.get("memory_policy_shards", []):
            if memory_shard.get("paper_allowed") is not False:
                errors.append(
                    f"{shard.get('shard_id')}:{memory_shard.get('memory_policy')}: "
                    "paper_allowed must be false"
                )
            if memory_shard.get("status") != "ready_smoke_shard":
                continue
            for key in ["config", "runner"]:
                path = Path(str(memory_shard.get(key, "")))
                if not path.exists():
                    errors.append(
                        f"{shard.get('shard_id')}:{memory_shard.get('memory_policy')}: "
                        f"missing {key}: {path}"
                    )
            if require_outputs:
                for key, value in (memory_shard.get("outputs") or {}).items():
                    if not Path(str(value)).exists():
                        errors.append(
                            f"{shard.get('shard_id')}:{memory_shard.get('memory_policy')}: "
                            f"missing output {key}: {value}"
                        )
        for calibration_shard in shard.get("calibration_shards", []):
            if calibration_shard.get("paper_allowed") is not False:
                errors.append(
                    f"{shard.get('shard_id')}:{calibration_shard.get('calibration')}: "
                    "paper_allowed must be false"
                )
            if calibration_shard.get("status") != "ready_smoke_shard":
                continue
            for key in ["config", "runner"]:
                path = Path(str(calibration_shard.get(key, "")))
                if not path.exists():
                    errors.append(
                        f"{shard.get('shard_id')}:{calibration_shard.get('calibration')}: "
                        f"missing {key}: {path}"
                    )
            if require_outputs:
                for key, value in (calibration_shard.get("outputs") or {}).items():
                    if not Path(str(value)).exists():
                        errors.append(
                            f"{shard.get('shard_id')}:{calibration_shard.get('calibration')}: "
                            f"missing output {key}: {value}"
                        )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="write a P0 shard plan manifest")
    plan.add_argument("p0_config", type=Path, nargs="?", default=Path("experiments/configs/p0.yaml"))
    plan.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)

    verify = subparsers.add_parser("verify", help="verify a P0 shard plan manifest")
    verify.add_argument("manifest", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    verify.add_argument("--require-outputs", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "plan":
        manifest = build_manifest(args.p0_config)
        write_manifest(args.output, manifest)
        print(args.output)
        print(
            "status="
            f"{manifest['status']} ready={manifest['ready_shard_count']}/{manifest['shard_count']} "
            f"calibration_ready={manifest['ready_calibration_shard_count']} "
            "paper_allowed=false"
        )
    elif args.command == "verify":
        manifest = json.loads(args.manifest.read_text())
        errors = verify_manifest(manifest, require_outputs=args.require_outputs)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            raise SystemExit(1)
        print(
            "p0 shard manifest valid: "
            f"{manifest.get('ready_shard_count')}/{manifest.get('shard_count')} ready, "
            f"{manifest.get('ready_calibration_shard_count', 0)} calibration shards ready, "
            "paper_allowed=false"
        )


if __name__ == "__main__":
    main()
