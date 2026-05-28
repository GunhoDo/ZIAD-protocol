#!/usr/bin/env python3
"""Build the compact stream-length sensitivity execution skeleton.

This is an appendix/sanity-check lane, not a full paper-candidate matrix. It
keeps paper and claim gates closed and writes only under
`results/latest/sensitivity/stream_length/`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow direct script execution.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for sensitivity config parsing") from error

from experiments import p0_full

DEFAULT_CONFIG = Path("experiments/configs/sensitivity/stream_length.yaml")
DEFAULT_OUTPUT_ROOT = Path("results/latest/sensitivity/stream_length")
DEFAULT_MANIFEST = DEFAULT_OUTPUT_ROOT / "manifest.json"
DEFAULT_EXECUTION_PLAN = DEFAULT_OUTPUT_ROOT / "execution_plan.json"
REQUIRED_METADATA = {
    "run_tier": "stream_length_sensitivity",
    "paper_allowed": False,
    "claim_allowed": False,
    "review_status": "review_pending",
}


def _load_config(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    if not isinstance(cfg, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return cfg


def _values(config: dict[str, Any], key: str) -> list[Any]:
    values = config.get(key)
    if not isinstance(values, list) or not values:
        raise SystemExit(f"stream-length sensitivity config axis is empty: {key}")
    return values


def _memory_policies(config: dict[str, Any], baseline: str) -> list[str]:
    policies = config.get("memory_policies", {}).get(baseline)
    if not isinstance(policies, list) or not policies:
        raise SystemExit(f"No memory policies configured for baseline: {baseline}")
    return [str(value) for value in policies]


def _validate_config(config: dict[str, Any]) -> None:
    for key, expected in REQUIRED_METADATA.items():
        if config.get(key) != expected:
            raise SystemExit(f"stream-length sensitivity config {key} must be {expected!r}")
    if config.get("evidence_scope") != "appendix_sanity_check":
        raise SystemExit("evidence_scope must be appendix_sanity_check")
    if config.get("dataset") != "MVTec AD":
        raise SystemExit("initial stream-length sensitivity scope is MVTec AD only")
    for key in [
        "baselines",
        "categories",
        "stream_lengths",
        "stream_types",
        "contamination_epsilon",
        "seeds",
        "calibration",
    ]:
        _values(config, key)
    for baseline in _values(config, "baselines"):
        _memory_policies(config, str(baseline))
    for length in _values(config, "stream_lengths"):
        if int(length) <= 20:
            raise SystemExit("stream_lengths must be non-validation values > 20")
    sampler = float(config.get("patchcore_sampler_percentage", 0.0))
    if not 0.0 < sampler <= 1.0:
        raise SystemExit("patchcore_sampler_percentage must be in (0, 1]")
    output_root = Path(str(config.get("output_root", DEFAULT_OUTPUT_ROOT)))
    if output_root.as_posix() != DEFAULT_OUTPUT_ROOT.as_posix():
        raise SystemExit(f"output_root must be {DEFAULT_OUTPUT_ROOT}")


def _output_root(
    config: dict[str, Any],
    *,
    baseline: str,
    memory_policy: str,
    calibration: str,
    category: str,
    stream_length: int,
) -> Path:
    return (
        Path(str(config.get("output_root", DEFAULT_OUTPUT_ROOT)))
        / p0_full._slug(str(config["dataset"]))
        / p0_full._slug(baseline)
        / p0_full._slug(memory_policy)
        / p0_full._slug(calibration)
        / p0_full._slug(category)
        / f"len_{stream_length}"
    )


def _step_id(
    *,
    dataset: str,
    baseline: str,
    memory_policy: str,
    calibration: str,
    category: str,
    stream_length: int,
) -> str:
    return ":".join(
        [
            p0_full._slug(dataset),
            p0_full._slug(baseline),
            p0_full._slug(memory_policy),
            p0_full._slug(calibration),
            p0_full._slug(category),
            f"len_{stream_length}",
        ]
    )


def build_manifest(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_config(config_path)
    _validate_config(config)
    dataset = str(config["dataset"])
    stream_types = [str(value) for value in config["stream_types"]]
    epsilons = [float(value) for value in config["contamination_epsilon"]]
    seeds = [int(value) for value in config["seeds"]]
    expected_rows = len(stream_types) * len(epsilons) * len(seeds)
    steps: list[dict[str, Any]] = []
    for baseline_value in config["baselines"]:
        baseline = str(baseline_value)
        for memory_policy in _memory_policies(config, baseline):
            for calibration_value in config["calibration"]:
                calibration = str(calibration_value)
                for category_value in config["categories"]:
                    category = str(category_value)
                    for length_value in config["stream_lengths"]:
                        stream_length = int(length_value)
                        root = _output_root(
                            config,
                            baseline=baseline,
                            memory_policy=memory_policy,
                            calibration=calibration,
                            category=category,
                            stream_length=stream_length,
                        )
                        step = {
                            **REQUIRED_METADATA,
                            "step_id": _step_id(
                                dataset=dataset,
                                baseline=baseline,
                                memory_policy=memory_policy,
                                calibration=calibration,
                                category=category,
                                stream_length=stream_length,
                            ),
                            "phase": "stream_length_sensitivity",
                            "source_tier": "stream_length_sensitivity",
                            "source_tier_role": "appendix_sanity_check",
                            "evidence_scope": "appendix_sanity_check",
                            "dataset": dataset,
                            "baseline": baseline,
                            "memory_policy": memory_policy,
                            "calibration": calibration,
                            "category": category,
                            "categories": [category],
                            "category_count": 1,
                            "stream_length": stream_length,
                            "stream_types": stream_types,
                            "contamination_epsilon": epsilons,
                            "seeds": seeds,
                            "prevalence": float(config.get("prevalence", 0.05)),
                            "expected_full_run_count": expected_rows,
                            "patchcore_sampler_percentage": float(
                                config["patchcore_sampler_percentage"]
                            ),
                            "output_root": str(root),
                            "outputs": p0_full._step_outputs(root),
                        }
                        steps.append(step)
    return {
        **REQUIRED_METADATA,
        "status": "stream_length_sensitivity_manifest_ready",
        "config": str(config_path),
        "output_root": str(config.get("output_root", DEFAULT_OUTPUT_ROOT)),
        "source_tier": "stream_length_sensitivity",
        "source_tier_role": "appendix_sanity_check",
        "evidence_scope": "appendix_sanity_check",
        "dataset": dataset,
        "baselines": [str(value) for value in config["baselines"]],
        "categories": [str(value) for value in config["categories"]],
        "stream_lengths": [int(value) for value in config["stream_lengths"]],
        "stream_types": stream_types,
        "contamination_epsilon": epsilons,
        "seeds": seeds,
        "calibration": [str(value) for value in config["calibration"]],
        "patchcore_sampler_percentage": float(config["patchcore_sampler_percentage"]),
        "step_count": len(steps),
        "row_count_if_complete": len(steps) * expected_rows,
        "expected_rows_per_step": expected_rows,
        "steps": steps,
        "notes": (
            "Appendix stream-length sensitivity scaffold only. Do not run the "
            "full sensitivity grid unless explicitly requested."
        ),
    }


def build_execution_plan(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    manifest = build_manifest(config_path)
    steps: list[dict[str, Any]] = []
    for step in manifest["steps"]:
        steps.append(
            {
                **step,
                "current_status": "pending_stream_length_sensitivity",
                "command": (
                    "python3 experiments/run_stream_length_sensitivity_step.py "
                    f"--step-id {step['step_id']}"
                ),
                "config": manifest["config"],
                "runner": "experiments/run_stream_length_sensitivity_step.py",
                "resume_policy": (
                    "Skip only when metrics.csv, manifest.json, and crd_lite.csv "
                    "exist and pass closed-gate row-count validation."
                ),
                "validation": {
                    "required_outputs": sorted(step["outputs"]),
                    "required_status": "measured_stream_length_sensitivity",
                    "expected_execution_mode": "production",
                    "expected_category_count": 1,
                    "expected_row_count_field": "expected_full_run_count",
                    "paper_allowed": False,
                    "claim_allowed": False,
                    "review_status": "review_pending",
                },
            }
        )
    return {
        **REQUIRED_METADATA,
        "status": "stream_length_sensitivity_execution_plan_ready",
        "config": manifest["config"],
        "output_root": manifest["output_root"],
        "source_tier": "stream_length_sensitivity",
        "source_tier_role": "appendix_sanity_check",
        "evidence_scope": "appendix_sanity_check",
        "step_count": len(steps),
        "pending_step_count": len(steps),
        "row_count_if_complete": manifest["row_count_if_complete"],
        "execution_order": [step["step_id"] for step in steps],
        "steps": steps,
        "notes": manifest["notes"],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--execution-plan", type=Path, default=DEFAULT_EXECUTION_PLAN)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args.config)
    execution_plan = build_execution_plan(args.config)
    write_json(args.manifest, manifest)
    write_json(args.execution_plan, execution_plan)
    print(args.manifest)
    print(args.execution_plan)
    print(
        "status="
        f"{execution_plan['status']} steps={execution_plan['step_count']} "
        f"row_count_if_complete={execution_plan['row_count_if_complete']} "
        "paper_allowed=false claim_allowed=false review_status=review_pending"
    )


if __name__ == "__main__":
    main()
