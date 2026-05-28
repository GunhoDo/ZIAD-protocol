#!/usr/bin/env python3
"""Execute or dry-run one stream-length sensitivity category shard."""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:  # Allow direct script execution.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments import run_p0_full_step, stream_length_sensitivity

DEFAULT_PLAN = Path("results/latest/sensitivity/stream_length/execution_plan.json")
SENSITIVITY_ROOT = Path("results/latest/sensitivity/stream_length")
REQUIRED_METADATA = dict(stream_length_sensitivity.REQUIRED_METADATA)
CommandRunner = Callable[[list[str]], int]


class StreamLengthSensitivityError(ValueError):
    """Raised when a sensitivity step is malformed or cannot run."""


def _as_posix(path: Path | str) -> str:
    return Path(str(path)).as_posix()


def _is_under_sensitivity_root(path: Path | str) -> bool:
    value = _as_posix(path)
    root = SENSITIVITY_ROOT.as_posix().rstrip("/") + "/"
    return value == SENSITIVITY_ROOT.as_posix() or value.startswith(root)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise StreamLengthSensitivityError(f"Missing stream-length sensitivity plan: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise StreamLengthSensitivityError(f"Plan must be a JSON object: {path}")
    return payload


def _enforce_metadata(payload: dict[str, Any], *, context: str) -> None:
    for key, expected in REQUIRED_METADATA.items():
        if payload.get(key) != expected:
            raise StreamLengthSensitivityError(f"{context} {key} must be {expected!r}")


def load_plan(path: Path = DEFAULT_PLAN) -> dict[str, Any]:
    plan = _load_json(path)
    _enforce_metadata(plan, context="execution plan")
    if plan.get("source_tier") != "stream_length_sensitivity":
        raise StreamLengthSensitivityError("source_tier must be stream_length_sensitivity")
    if plan.get("output_root") and not _is_under_sensitivity_root(plan["output_root"]):
        raise StreamLengthSensitivityError(
            f"plan output_root is outside {SENSITIVITY_ROOT}"
        )
    if not isinstance(plan.get("steps"), list):
        raise StreamLengthSensitivityError("execution plan must contain steps")
    return plan


def _read_metric_row(path: Path, *, run_dir: Path) -> dict[str, str]:
    if not path.exists():
        raise run_p0_full_step.FullP0StepError(f"Expected metrics output missing: {path}")
    with path.open(newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if len(rows) != 1:
        raise run_p0_full_step.FullP0StepError(
            f"Expected one metric row in {path}, got {len(rows)}"
        )
    row = rows[0]
    row["run_dir"] = str(run_dir)
    row["status"] = "measured_stream_length_sensitivity"
    return row


def _build_manifest_metadata(step: dict[str, Any]) -> dict[str, Any]:
    return {
        **REQUIRED_METADATA,
        "status": "not_run",
        "step_id": str(step.get("step_id", "")),
        "dataset": str(step.get("dataset", "")),
        "baseline": str(step.get("baseline", "")),
        "memory_policy": str(step.get("memory_policy", "")),
        "calibration": str(step.get("calibration", "")),
        "category": str(step.get("category", "")),
        "stream_length": int(step.get("stream_length", 0)),
        "source_tier": "stream_length_sensitivity",
        "source_tier_role": "appendix_sanity_check",
        "evidence_scope": "appendix_sanity_check",
    }


def _build_latest_run_metadata(step: dict[str, Any]) -> dict[str, Any]:
    return {
        **_build_manifest_metadata(step),
        "run_scope": "stream_length_sensitivity_category_shard",
    }


def _configure_full_step_module(step: dict[str, Any] | None = None) -> None:
    run_p0_full_step.FULL_OUTPUT_ROOT = SENSITIVITY_ROOT
    run_p0_full_step.REQUIRED_METADATA = dict(REQUIRED_METADATA)
    run_p0_full_step._read_metric_row = _read_metric_row
    run_p0_full_step.build_manifest_metadata = _build_manifest_metadata
    run_p0_full_step.build_latest_run_metadata = _build_latest_run_metadata
    if step is not None:
        run_p0_full_step.ALLOWED_PRODUCTION_STEP_IDS = {
            *run_p0_full_step.ALLOWED_PRODUCTION_STEP_IDS,
            str(step.get("step_id", "")),
        }
        run_p0_full_step.PATCHCORE_PRODUCTION_VALIDATION_SAMPLER_PERCENTAGE = float(
            step.get("patchcore_sampler_percentage", 0.1)
        )


def _outputs_exist(step: dict[str, Any]) -> bool:
    return all(Path(str(path)).exists() for path in step.get("outputs", {}).values())


def _has_partial_output(step: dict[str, Any]) -> bool:
    root = Path(str(step.get("output_root", "")))
    return root.exists() and any(root.iterdir()) and not _outputs_exist(step)


def validate_step_contract(step: dict[str, Any], *, output_root: Path | None = None) -> None:
    _enforce_metadata(step, context=f"step {step.get('step_id', '<unknown>')}")
    if step.get("source_tier") != "stream_length_sensitivity":
        raise StreamLengthSensitivityError("step source_tier must be stream_length_sensitivity")
    declared_root = step.get("output_root")
    if not declared_root or not _is_under_sensitivity_root(str(declared_root)):
        raise StreamLengthSensitivityError(
            f"step output_root is outside {SENSITIVITY_ROOT}: {declared_root}"
        )
    if output_root is not None and _as_posix(output_root) != _as_posix(declared_root):
        raise StreamLengthSensitivityError(
            f"requested output root does not match selected step: {output_root} != {declared_root}"
        )
    for key, path in step.get("outputs", {}).items():
        if not _is_under_sensitivity_root(str(path)):
            raise StreamLengthSensitivityError(
                f"output path for {key} is outside {SENSITIVITY_ROOT}: {path}"
            )
    validation = step.get("validation")
    if not isinstance(validation, dict):
        raise StreamLengthSensitivityError("step must declare a validation gate")
    if validation.get("paper_allowed") is not False:
        raise StreamLengthSensitivityError("validation paper_allowed must be false")
    if validation.get("claim_allowed") is not False:
        raise StreamLengthSensitivityError("validation claim_allowed must be false")
    if validation.get("review_status") != "review_pending":
        raise StreamLengthSensitivityError("validation review_status must be review_pending")


def verify_completed_step(step: dict[str, Any]) -> None:
    _configure_full_step_module(step)
    run_p0_full_step.verify_completed_step(step, completion_mode="production")
    metrics_path = Path(str(step["outputs"]["aggregate_metrics"]))
    with metrics_path.open(newline="") as handle:
        statuses = {row.get("status") for row in csv.DictReader(handle)}
    if statuses != {"measured_stream_length_sensitivity"}:
        raise StreamLengthSensitivityError(
            "sensitivity metrics status must be measured_stream_length_sensitivity, "
            f"got {statuses}"
        )
    manifest = _load_json(Path(str(step["outputs"]["aggregate_manifest"])))
    _enforce_metadata(manifest, context="aggregate manifest")
    if manifest.get("status") != "measured_stream_length_sensitivity_complete":
        raise StreamLengthSensitivityError("aggregate manifest is not sensitivity-complete")
    if manifest.get("evidence_scope") != "appendix_sanity_check":
        raise StreamLengthSensitivityError("aggregate manifest evidence_scope mismatch")
    if manifest.get("category") != step.get("category"):
        raise StreamLengthSensitivityError("aggregate manifest category mismatch")
    if int(manifest.get("stream_length", 0)) != int(step.get("stream_length", 0)):
        raise StreamLengthSensitivityError("aggregate manifest stream_length mismatch")


def _patch_manifest_status(step: dict[str, Any]) -> None:
    manifest_path = Path(str(step["outputs"]["aggregate_manifest"]))
    manifest = _load_json(manifest_path)
    manifest.update(
        {
            **REQUIRED_METADATA,
            "status": "measured_stream_length_sensitivity_complete",
            "execution_mode": "production",
            "evidence_scope": "appendix_sanity_check",
            "source_tier": "stream_length_sensitivity",
            "source_tier_role": "appendix_sanity_check",
            "category": step.get("category"),
            "stream_length": int(step.get("stream_length", 0)),
            "notes": (
                "Appendix stream-length sensitivity shard. This is not a main "
                "paper result and does not open paper or claim gates."
            ),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def run_step(
    plan: dict[str, Any],
    *,
    selector: str,
    output_root: Path | None = None,
    dry_run: bool = False,
    command_runner: CommandRunner = run_p0_full_step._default_command_runner,
) -> tuple[int, dict[str, Any]]:
    index, step = run_p0_full_step.resolve_step(plan, selector)
    validate_step_contract(step, output_root=output_root)
    _configure_full_step_module(step)
    stream_length = int(step["stream_length"])

    if dry_run:
        status = "complete" if _outputs_exist(step) else "pending"
        print(
            f"[{index}] DRY-RUN stream-length sensitivity {step['step_id']}: "
            f"{status} output_root={step['output_root']}"
        )
        return index, step
    if _has_partial_output(step):
        raise StreamLengthSensitivityError(
            f"partial sensitivity output exists but is not complete: {step['output_root']}"
        )
    if _outputs_exist(step):
        verify_completed_step(step)
        print(f"[{index}] SKIP complete stream-length sensitivity {step['step_id']}")
        return index, step

    local_plan = dict(plan)
    local_plan["steps"] = [step]
    run_p0_full_step.run_step(
        local_plan,
        selector=step["step_id"],
        output_root=Path(str(step["output_root"])),
        stream_length=stream_length,
        command_runner=command_runner,
    )
    _patch_manifest_status(step)
    verify_completed_step(step)
    print(
        f"[{index}] COMPLETE stream-length sensitivity {step['step_id']}: "
        f"stream_length={stream_length}"
    )
    return index, step


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--step", help="Step id or zero-based index")
    selector.add_argument("--step-id", help="Step id")
    selector.add_argument("--index", type=int, help="Zero-based step index")
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
            command_runner=run_p0_full_step._default_command_runner,
        )
    except (
        json.JSONDecodeError,
        OSError,
        StreamLengthSensitivityError,
        run_p0_full_step.FullP0StepError,
    ) as error:
        raise SystemExit(f"ERROR: {error}") from error
    print(
        "selected_step="
        f"{index} step_id={step['step_id']} run_tier=stream_length_sensitivity "
        "paper_allowed=false claim_allowed=false review_status=review_pending"
    )


if __name__ == "__main__":
    main()
