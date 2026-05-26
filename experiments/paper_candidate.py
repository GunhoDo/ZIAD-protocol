#!/usr/bin/env python3
"""Build a separate paper-candidate execution skeleton.

The paper-candidate skeleton reuses the compact full-P0 matrix shape, but
writes only under `results/latest/paper_candidate/` and keeps both claim gates
closed until manual review promotes any result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/paper_candidate.py ...`.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError as error:  # pragma: no cover - environment-dependent
    raise SystemExit("PyYAML is required for paper-candidate config parsing") from error

from experiments import p0_full

DEFAULT_CONFIG = Path("experiments/configs/paper_candidate/compact.yaml")
DEFAULT_MANIFEST = Path("results/latest/paper_candidate/manifest.json")
DEFAULT_EXECUTION_PLAN = Path("results/latest/paper_candidate/execution_plan.json")
DEFAULT_OUTPUT_ROOT = Path("results/latest/paper_candidate")


def _load_config(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    if not isinstance(cfg, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return cfg


def _validate_config(config: dict[str, Any]) -> None:
    if config.get("run_tier") != "paper_candidate":
        raise SystemExit("paper-candidate config run_tier must be paper_candidate")
    if config.get("paper_allowed") is not False:
        raise SystemExit("paper-candidate config paper_allowed must be false")
    if config.get("claim_allowed") is not False:
        raise SystemExit("paper-candidate config claim_allowed must be false")
    if config.get("review_status") != "review_pending":
        raise SystemExit("paper-candidate config review_status must be review_pending")
    if config.get("source_tier") == "smoke":
        raise SystemExit("paper-candidate source_tier must not be smoke")
    if int(config.get("paper_candidate_stream_length", 0)) <= 20:
        raise SystemExit("paper_candidate_stream_length must be a non-validation value > 20")
    sampler = float(config.get("patchcore_sampler_percentage", 0.0))
    if not 0.0 < sampler <= 1.0:
        raise SystemExit("patchcore_sampler_percentage must be in (0, 1]")

    axes = p0_full._matrix_axes(config)
    for name, values in axes.items():
        if not values:
            raise SystemExit(f"paper-candidate config axis is empty: {name}")
    for baseline in axes["baselines"]:
        p0_full._memory_policies(config, baseline)
    candidate_scope = str(config.get("candidate_scope", "full_category"))
    if candidate_scope not in {"full_category", "first_category_pilot", "category_shard"}:
        raise SystemExit(
            "candidate_scope must be full_category, first_category_pilot, or category_shard"
        )
    if candidate_scope == "first_category_pilot":
        candidate_categories = config.get("candidate_categories")
        if not isinstance(candidate_categories, dict):
            raise SystemExit("first_category_pilot requires candidate_categories")
        for dataset in axes["datasets"]:
            values = candidate_categories.get(dataset)
            if not isinstance(values, list) or len(values) != 1:
                raise SystemExit(
                    f"first_category_pilot requires exactly one category for {dataset}"
                )


def _step_output_root(
    config: dict[str, Any],
    dataset: str,
    baseline: str,
    memory_policy: str,
    calibration: str,
) -> Path:
    output_root = Path(str(config.get("output_root", DEFAULT_OUTPUT_ROOT)))
    return (
        output_root
        / p0_full._slug(dataset)
        / p0_full._slug(baseline)
        / p0_full._slug(memory_policy)
        / p0_full._slug(calibration)
    )


def _candidate_categories(config: dict[str, Any], dataset: str) -> list[str]:
    if str(config.get("candidate_scope", "full_category")) == "first_category_pilot":
        categories = config.get("candidate_categories", {}).get(dataset, [])
        return [str(value) for value in categories]
    return p0_full._full_categories(dataset)


def production_run_count(config: dict[str, Any]) -> int:
    axes = p0_full._matrix_axes(config)
    baseline_policy_count = sum(
        len(p0_full._memory_policies(config, baseline))
        for baseline in axes["baselines"]
    )
    category_count = sum(
        len(_candidate_categories(config, dataset)) for dataset in axes["datasets"]
    )
    return (
        category_count
        * baseline_policy_count
        * len(axes["stream_types"])
        * len(axes["contamination_epsilon"])
        * len(axes["calibration"])
        * len(axes["seeds"])
    )


def build_manifest(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_config(config_path)
    _validate_config(config)
    axes = p0_full._matrix_axes(config)
    steps: list[dict[str, Any]] = []
    for dataset in axes["datasets"]:
        categories = _candidate_categories(config, dataset)
        for baseline in axes["baselines"]:
            for memory_policy in p0_full._memory_policies(config, baseline):
                for calibration in axes["calibration"]:
                    step_root = _step_output_root(
                        config,
                        dataset,
                        baseline,
                        memory_policy,
                        calibration,
                    )
                    step_id = (
                        f"{p0_full._slug(dataset)}:{p0_full._slug(baseline)}:"
                        f"{p0_full._slug(memory_policy)}:{p0_full._slug(calibration)}"
                    )
                    expected_full_run_count = (
                        len(categories)
                        * len(axes["stream_types"])
                        * len(axes["contamination_epsilon"])
                        * len(axes["seeds"])
                    )
                    expected_category_shard_run_count = (
                        len(axes["stream_types"])
                        * len(axes["contamination_epsilon"])
                        * len(axes["seeds"])
                    )
                    steps.append(
                        {
                            "step_id": step_id,
                            "run_tier": "paper_candidate",
                            "source_tier": "paper_candidate",
                            "source_tier_role": "primary_candidate_output",
                            "paper_allowed": False,
                            "claim_allowed": False,
                            "review_status": "review_pending",
                            "dataset": dataset,
                            "baseline": baseline,
                            "memory_policy": memory_policy,
                            "calibration": calibration,
                            "categories": categories,
                            "category_count": len(categories),
                            "stream_types": axes["stream_types"],
                            "contamination_epsilon": axes["contamination_epsilon"],
                            "seeds": axes["seeds"],
                            "expected_full_run_count": expected_full_run_count,
                            "expected_category_shard_run_count": (
                                expected_category_shard_run_count
                            ),
                            "paper_candidate_stream_length": int(
                                config["paper_candidate_stream_length"]
                            ),
                            "patchcore_sampler_percentage": float(
                                config["patchcore_sampler_percentage"]
                            ),
                            "candidate_scope": str(config.get("candidate_scope", "full_category")),
                            "full_p0_category_count": len(p0_full._full_categories(dataset)),
                            "output_root": str(step_root),
                            "outputs": p0_full._step_outputs(step_root),
                        }
                    )
    return {
        "status": "paper_candidate_skeleton_ready",
        "run_tier": "paper_candidate",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "config": str(config_path),
        "output_root": str(config["output_root"]),
        "source_tier": "paper_candidate",
        "source_tier_role": "primary_candidate_output",
        "paper_candidate_stream_length": int(config["paper_candidate_stream_length"]),
        "patchcore_sampler_percentage": float(config["patchcore_sampler_percentage"]),
        "candidate_scope": str(config.get("candidate_scope", "full_category")),
        "candidate_categories": config.get("candidate_categories", {}),
        "matrix_axes": {
            **axes,
            "memory_policies": {
                baseline: p0_full._memory_policies(config, baseline)
                for baseline in axes["baselines"]
            },
        },
        "matrix_count": p0_full.matrix_count(config),
        "production_matrix_count": production_run_count(config),
        "step_count": len(steps),
        "steps": steps,
        "notes": (
            "Paper-candidate skeleton only. Outputs are separate from "
            "results/latest/p0_full validation artifacts and still require "
            "manual review before any paper promotion."
        ),
    }


def build_execution_plan(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    manifest = build_manifest(config_path)
    steps: list[dict[str, Any]] = []
    stream_length = int(manifest["paper_candidate_stream_length"])
    for step in manifest["steps"]:
        steps.append(
            {
                "step_id": step["step_id"],
                "phase": "paper_candidate_compact",
                "run_tier": "paper_candidate",
                "source_tier": "paper_candidate",
                "source_tier_role": "primary_candidate_output",
                "paper_allowed": False,
                "claim_allowed": False,
                "review_status": "review_pending",
                "current_status": "pending_paper_candidate_execution",
                "dataset": step["dataset"],
                "baseline": step["baseline"],
                "memory_policy": step["memory_policy"],
                "calibration": step["calibration"],
                "categories": step["categories"],
                "category_count": step["category_count"],
                "stream_types": step["stream_types"],
                "contamination_epsilon": step["contamination_epsilon"],
                "seeds": step["seeds"],
                "expected_full_run_count": step["expected_full_run_count"],
                "expected_category_shard_run_count": step[
                    "expected_category_shard_run_count"
                ],
                "paper_candidate_stream_length": stream_length,
                "patchcore_sampler_percentage": step["patchcore_sampler_percentage"],
                "candidate_scope": step["candidate_scope"],
                "full_p0_category_count": step["full_p0_category_count"],
                "output_root": step["output_root"],
                "command": (
                    "python3 experiments/run_paper_candidate_step.py "
                    "--plan results/latest/paper_candidate/execution_plan.json "
                    f"--step-id {step['step_id']} "
                    "--category <category> "
                    f"--stream-length {stream_length}"
                ),
                "config": str(config_path),
                "runner": "experiments/run_paper_candidate_step.py",
                "outputs": step["outputs"],
                "depends_on": [],
                "resume_policy": (
                    "Skip only when declared paper_candidate aggregate outputs exist "
                    "and pass paper_allowed=false, claim_allowed=false, "
                    "review_status=review_pending, and row-count validation."
                ),
                "validation": {
                    "required_outputs": sorted(step["outputs"]),
                    "required_status": "measured_paper_candidate",
                    "expected_execution_mode": "production",
                    "expected_category_count": step["category_count"],
                    "expected_row_count_field": "expected_full_run_count",
                    "expected_category_shard_row_count_field": (
                        "expected_category_shard_run_count"
                    ),
                    "paper_allowed": False,
                    "claim_allowed": False,
                    "review_status": "review_pending",
                    "notes": (
                        "Validation/full-P0 outputs must not satisfy this step. "
                        "Required outputs must live under results/latest/paper_candidate/."
                    ),
                },
            }
        )
    return {
        "status": "paper_candidate_execution_plan_ready",
        "run_tier": "paper_candidate",
        "paper_allowed": False,
        "claim_allowed": False,
        "review_status": "review_pending",
        "config": manifest["config"],
        "output_root": manifest["output_root"],
        "source_tier": "paper_candidate",
        "source_tier_role": "primary_candidate_output",
        "paper_candidate_stream_length": stream_length,
        "patchcore_sampler_percentage": manifest["patchcore_sampler_percentage"],
        "candidate_scope": manifest["candidate_scope"],
        "matrix_count": manifest["matrix_count"],
        "production_matrix_count": manifest["production_matrix_count"],
        "step_count": len(steps),
        "ready_step_count": 0,
        "pending_step_count": len(steps),
        "phase_counts": {"paper_candidate_compact": len(steps)},
        "execution_order": [step["step_id"] for step in steps],
        "steps": steps,
        "notes": (
            "Paper-candidate execution plan. Run single steps first; do not "
            "promote outputs until manual review completes."
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
        f"matrix_count={execution_plan['matrix_count']} "
        f"stream_length={execution_plan['paper_candidate_stream_length']} "
        "paper_allowed=false claim_allowed=false review_status=review_pending"
    )


if __name__ == "__main__":
    main()
