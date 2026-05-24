#!/usr/bin/env python3
"""Build a separate full-P0 execution skeleton.

The full-P0 skeleton is intentionally independent from the current smoke shard
artifacts. It defines reviewed-P0 output paths under `results/latest/p0_full/`
and keeps every gate closed until future full inference and review happen.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/p0_full.py ...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for full-P0 config parsing") from error

DEFAULT_CONFIG = Path("experiments/configs/p0_full/compact.yaml")
DEFAULT_MANIFEST = Path("results/latest/p0_full/manifest.json")
DEFAULT_EXECUTION_PLAN = Path("results/latest/p0_full/execution_plan.json")


def _load_config(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    if not isinstance(cfg, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return cfg


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _memory_policies(config: dict[str, Any], baseline: str) -> list[str]:
    policies = config.get("memory_policies", {})
    if not isinstance(policies, dict):
        raise SystemExit("memory_policies must be a mapping keyed by baseline")
    values = policies.get(baseline)
    if values is None:
        raise SystemExit(f"Missing memory policy list for baseline: {baseline}")
    return [str(value) for value in _as_list(values)]


def _matrix_axes(config: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "datasets": [str(value) for value in _as_list(config.get("datasets"))],
        "baselines": [str(value) for value in _as_list(config.get("baselines"))],
        "stream_types": [str(value) for value in _as_list(config.get("stream_types"))],
        "contamination_epsilon": [
            str(value) for value in _as_list(config.get("contamination_epsilon"))
        ],
        "calibration": [str(value) for value in _as_list(config.get("calibration"))],
        "seeds": [str(value) for value in _as_list(config.get("seeds"))],
    }


def _validate_config(config: dict[str, Any]) -> None:
    if config.get("run_tier") != "p0_full":
        raise SystemExit("full-P0 config run_tier must be p0_full")
    if config.get("paper_allowed") is not False:
        raise SystemExit("full-P0 config paper_allowed must be false")
    if config.get("claim_allowed") is not False:
        raise SystemExit("full-P0 config claim_allowed must be false")
    if config.get("review_status") not in {"not_reviewed", "review_pending"}:
        raise SystemExit("full-P0 config review_status must be not_reviewed or review_pending")
    if config.get("source_tier") == "smoke":
        raise SystemExit("full-P0 source_tier must not be smoke")
    axes = _matrix_axes(config)
    for name, values in axes.items():
        if not values:
            raise SystemExit(f"full-P0 config axis is empty: {name}")
    for baseline in axes["baselines"]:
        _memory_policies(config, baseline)


def matrix_count(config: dict[str, Any]) -> int:
    axes = _matrix_axes(config)
    baseline_policy_count = sum(
        len(_memory_policies(config, baseline)) for baseline in axes["baselines"]
    )
    return (
        len(axes["datasets"])
        * baseline_policy_count
        * len(axes["stream_types"])
        * len(axes["contamination_epsilon"])
        * len(axes["calibration"])
        * len(axes["seeds"])
    )


def _step_output_root(
    config: dict[str, Any],
    dataset: str,
    baseline: str,
    memory_policy: str,
    calibration: str,
) -> Path:
    output_root = Path(str(config.get("output_root", "results/latest/p0_full")))
    return (
        output_root
        / _slug(dataset)
        / _slug(baseline)
        / _slug(memory_policy)
        / _slug(calibration)
    )


def _step_outputs(root: Path) -> dict[str, str]:
    return {
        "aggregate_metrics": str(root / "metrics.csv"),
        "aggregate_manifest": str(root / "manifest.json"),
        "crd_lite_summary": str(root / "crd_lite.csv"),
    }


def build_manifest(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_config(config_path)
    _validate_config(config)
    axes = _matrix_axes(config)
    steps = []
    for dataset in axes["datasets"]:
        for baseline in axes["baselines"]:
            for memory_policy in _memory_policies(config, baseline):
                for calibration in axes["calibration"]:
                    step_root = _step_output_root(
                        config, dataset, baseline, memory_policy, calibration
                    )
                    step_id = (
                        f"{_slug(dataset)}:{_slug(baseline)}:"
                        f"{_slug(memory_policy)}:{_slug(calibration)}"
                    )
                    steps.append(
                        {
                            "step_id": step_id,
                            "run_tier": "p0_full",
                            "source_tier": "p0_full",
                            "source_tier_role": "primary_full_output",
                            "paper_allowed": False,
                            "claim_allowed": False,
                            "review_status": str(config["review_status"]),
                            "dataset": dataset,
                            "baseline": baseline,
                            "memory_policy": memory_policy,
                            "calibration": calibration,
                            "stream_types": axes["stream_types"],
                            "contamination_epsilon": axes["contamination_epsilon"],
                            "seeds": axes["seeds"],
                            "expected_full_run_count": (
                                len(axes["stream_types"])
                                * len(axes["contamination_epsilon"])
                                * len(axes["seeds"])
                            ),
                            "output_root": str(step_root),
                            "outputs": _step_outputs(step_root),
                        }
                    )
    return {
        "status": "p0_full_skeleton_ready",
        "run_tier": "p0_full",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": str(config["review_status"]),
        "config": str(config_path),
        "output_root": str(config["output_root"]),
        "source_tier": str(config["source_tier"]),
        "source_tier_role": "primary_full_output",
        "matrix_axes": {
            **axes,
            "memory_policies": {
                baseline: _memory_policies(config, baseline)
                for baseline in axes["baselines"]
            },
        },
        "matrix_count": matrix_count(config),
        "step_count": len(steps),
        "steps": steps,
        "notes": (
            "Full-P0 skeleton only. Outputs are intentionally separate from "
            "results/latest/p0_shards smoke artifacts and have not been run or reviewed."
        ),
    }


def build_execution_plan(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    manifest = build_manifest(config_path)
    steps = []
    for step in manifest["steps"]:
        steps.append(
            {
                "step_id": step["step_id"],
                "phase": "p0_full_compact",
                "run_tier": "p0_full",
                "source_tier": "p0_full",
                "source_tier_role": "primary_full_output",
                "paper_allowed": False,
                "claim_allowed": False,
                "review_status": step["review_status"],
                "current_status": "pending_full_p0_execution",
                "dataset": step["dataset"],
                "baseline": step["baseline"],
                "memory_policy": step["memory_policy"],
                "calibration": step["calibration"],
                "stream_types": step["stream_types"],
                "contamination_epsilon": step["contamination_epsilon"],
                "seeds": step["seeds"],
                "expected_smoke_run_count": step["expected_full_run_count"],
                "expected_full_run_count": step["expected_full_run_count"],
                "command": (
                    "python3 experiments/run_p0_full_step.py "
                    f"--step-id {step['step_id']} "
                    f"--output-root {step['output_root']}"
                ),
                "config": str(config_path),
                "runner": "experiments/run_p0_full_step.py",
                "outputs": step["outputs"],
                "depends_on": [],
                "resume_policy": (
                    "Skip only when declared p0_full aggregate outputs exist and pass "
                    "paper_allowed=false, claim_allowed=false, and row-count validation."
                ),
                "validation": {
                    "required_outputs": sorted(step["outputs"]),
                    "required_status": "measured_full_p0",
                    "paper_allowed": False,
                    "claim_allowed": False,
                    "review_status": step["review_status"],
                    "notes": (
                        "Smoke outputs must not satisfy this step. Required outputs "
                        "must live under results/latest/p0_full/."
                    ),
                },
            }
        )
    return {
        "status": "p0_full_execution_plan_skeleton_ready",
        "run_tier": "p0_full",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": manifest["review_status"],
        "config": str(config_path),
        "output_root": manifest["output_root"],
        "source_tier": "p0_full",
        "source_tier_role": "primary_full_output",
        "matrix_count": manifest["matrix_count"],
        "step_count": len(steps),
        "ready_step_count": 0,
        "pending_step_count": len(steps),
        "phase_counts": {"p0_full_compact": len(steps)},
        "execution_order": [step["step_id"] for step in steps],
        "steps": steps,
        "notes": (
            "Full-P0 execution skeleton only. It is dry-run compatible with "
            "experiments/run_p0_execution_plan.py, but the full runner command is "
            "not implemented and full inference has not been run."
        ),
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
        f"matrix_count={execution_plan['matrix_count']} paper_allowed=false"
    )


if __name__ == "__main__":
    main()
