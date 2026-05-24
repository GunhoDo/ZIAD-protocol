#!/usr/bin/env python3
"""Execute or dry-run one compact full-P0 aggregate step.

This is the single-step boundary for the future reviewed P0 run. It resolves
one step from `results/latest/p0_full/execution_plan.json`, validates that every
declared output stays under `results/latest/p0_full/`, and keeps all paper gates
closed. The real full-inference body is intentionally not implemented yet; use
`--dry-run` to inspect the selected step without producing outputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_PLAN = Path("results/latest/p0_full/execution_plan.json")
FULL_OUTPUT_ROOT = Path("results/latest/p0_full")
REQUIRED_METADATA = {
    "run_tier": "p0_full",
    "paper_allowed": False,
    "claim_allowed": False,
    "review_status": "not_reviewed",
}


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


def run_step(
    plan: dict[str, Any],
    *,
    selector: str,
    output_root: Path | None = None,
    dry_run: bool = False,
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

    raise FullP0StepError(
        "Full-P0 real inference is not implemented yet; rerun with --dry-run "
        "or implement the measured full-P0 step body before executing."
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
