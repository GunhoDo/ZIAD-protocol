#!/usr/bin/env python3
"""Execute or dry-run one paper-candidate aggregate step.

This runner intentionally targets `results/latest/paper_candidate/` and keeps
both paper gates closed. It reuses the proven full-P0 single-step execution
body, but swaps the metadata envelope and aggregate row status to the
paper-candidate tier.
"""
from __future__ import annotations

import argparse
import csv
import copy
import json
import time
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:  # Allow `python3 experiments/run_paper_candidate_step.py ...`.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments import run_p0_full_step
from experiments import p0_full

DEFAULT_PLAN = Path("results/latest/paper_candidate/execution_plan.json")
PAPER_CANDIDATE_ROOT = Path("results/latest/paper_candidate")
REQUIRED_METADATA = {
    "run_tier": "paper_candidate",
    "paper_allowed": False,
    "claim_allowed": False,
    "review_status": "review_pending",
}
CommandRunner = Callable[[list[str]], int]


class PaperCandidateStepError(ValueError):
    """Raised when a paper-candidate step is malformed or cannot run."""


def _as_posix(path: Path | str) -> str:
    return Path(str(path)).as_posix()


def _is_under_candidate_root(path: Path | str) -> bool:
    value = _as_posix(path)
    root = PAPER_CANDIDATE_ROOT.as_posix().rstrip("/") + "/"
    return value == PAPER_CANDIDATE_ROOT.as_posix() or value.startswith(root)


def _shard_root(base_output_root: Path | str, category: str) -> Path:
    return Path(str(base_output_root)) / p0_full._slug(category)


def _step_outputs(root: Path) -> dict[str, str]:
    return {
        "aggregate_metrics": str(root / "metrics.csv"),
        "aggregate_manifest": str(root / "manifest.json"),
        "crd_lite_summary": str(root / "crd_lite.csv"),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PaperCandidateStepError(f"Missing paper-candidate execution plan: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise PaperCandidateStepError(f"Execution plan must be a JSON object: {path}")
    return payload


def _normalized_seeds(values: Any) -> list[int]:
    return [int(value) for value in (values or [])]


def _enforce_metadata(payload: dict[str, Any], *, context: str) -> None:
    for key, expected in REQUIRED_METADATA.items():
        if payload.get(key) != expected:
            raise PaperCandidateStepError(f"{context} {key} must be {expected!r}")


def load_plan(path: Path = DEFAULT_PLAN) -> dict[str, Any]:
    plan = _load_json(path)
    _enforce_metadata(plan, context="execution plan")
    if plan.get("source_tier") == "smoke":
        raise PaperCandidateStepError("paper-candidate source_tier must not be smoke")
    if plan.get("output_root") and not _is_under_candidate_root(str(plan["output_root"])):
        raise PaperCandidateStepError(
            f"paper-candidate plan output_root is outside {PAPER_CANDIDATE_ROOT}"
        )
    if not isinstance(plan.get("steps"), list):
        raise PaperCandidateStepError("paper-candidate execution plan must contain steps")
    return plan


def _read_metric_row(path: Path, *, run_dir: Path) -> dict[str, str]:
    if not path.exists():
        raise run_p0_full_step.FullP0StepError(f"Expected metrics output was not created: {path}")
    with path.open(newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if len(rows) != 1:
        raise run_p0_full_step.FullP0StepError(
            f"Expected one metric row in {path}, got {len(rows)}"
        )
    row = rows[0]
    row["run_dir"] = str(run_dir)
    row["status"] = "measured_paper_candidate"
    return row


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
        **run_p0_full_step.build_latest_run_metadata(step),
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
        "notes": (
            "Single-step paper-candidate production output; paper and claim "
            "gates remain closed pending manual review."
        ),
    }


def _configure_full_step_module(plan: dict[str, Any]) -> None:
    run_p0_full_step.FULL_OUTPUT_ROOT = PAPER_CANDIDATE_ROOT
    run_p0_full_step.REQUIRED_METADATA = dict(REQUIRED_METADATA)
    run_p0_full_step._read_metric_row = _read_metric_row
    run_p0_full_step._run_provenance = _run_provenance
    run_p0_full_step.PATCHCORE_PRODUCTION_VALIDATION_SAMPLER_PERCENTAGE = float(
        plan.get("patchcore_sampler_percentage", 0.1)
    )


def _patch_manifest_status(step: dict[str, Any], *, stream_length: int) -> None:
    manifest_path = Path(str(step["outputs"]["aggregate_manifest"]))
    manifest = _load_json(manifest_path)
    manifest.update(
        {
            **REQUIRED_METADATA,
            "status": "measured_paper_candidate_production_complete",
            "execution_mode": "production",
            "paper_candidate_stream_length": stream_length,
            "candidate_scope": step.get("candidate_scope", "full_category"),
            "category": step.get("category"),
            "seeds": _normalized_seeds(step.get("seeds")),
            "full_p0_category_count": step.get("full_p0_category_count"),
            "notes": (
                "Single paper-candidate production step. This is not a paper "
                "result until manual review explicitly promotes it."
            ),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def prepare_category_shard_step(
    step: dict[str, Any],
    *,
    category: str,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Return a single-category copy of a paper-candidate aggregate step."""
    if not category:
        raise PaperCandidateStepError("category-shard paper-candidate execution requires --category")
    categories = [str(value) for value in step.get("categories", [])]
    if category not in categories:
        raise PaperCandidateStepError(
            f"category {category!r} is not declared for step {step.get('step_id')}"
        )
    base_root = Path(str(step.get("output_root", "")))
    expected_root = _shard_root(base_root, category)
    if output_root is not None and _as_posix(output_root) != _as_posix(expected_root):
        raise PaperCandidateStepError(
            "category-shard output_root must include the category: "
            f"{output_root} != {expected_root}"
        )
    selected = copy.deepcopy(step)
    selected["candidate_scope"] = "category_shard"
    selected["category"] = category
    selected["categories"] = [category]
    selected["category_count"] = 1
    selected["full_p0_category_count"] = int(
        step.get("full_p0_category_count") or len(categories)
    )
    selected["expected_full_run_count"] = int(
        step.get("expected_category_shard_run_count")
        or (
            len(step.get("stream_types", []))
            * len(step.get("contamination_epsilon", []))
            * len(step.get("seeds", []))
        )
    )
    selected["output_root"] = str(expected_root)
    selected["outputs"] = _step_outputs(expected_root)
    validation = dict(selected.get("validation", {}))
    validation["expected_category_count"] = 1
    validation["expected_row_count_field"] = "expected_full_run_count"
    selected["validation"] = validation
    return selected


def _has_any_output(root: Path) -> bool:
    if not root.exists():
        return False
    return any(root.iterdir())


def _outputs_exist(step: dict[str, Any]) -> bool:
    outputs = step.get("outputs", {})
    return all(Path(str(path)).exists() for path in outputs.values())


def _raise_on_partial_outputs(step: dict[str, Any]) -> None:
    root = Path(str(step["output_root"]))
    if not _has_any_output(root) or _outputs_exist(step):
        return
    production_runs = root / "production_runs"
    run_dirs = [path for path in production_runs.iterdir() if path.is_dir()] if production_runs.is_dir() else []
    complete_run_dirs = [
        path
        for path in run_dirs
        if (path / "scores.csv").exists()
        and (path / "latest_run.json").exists()
        and (path / "manifest.json").exists()
        and (path / "metrics.csv").exists()
    ]
    if complete_run_dirs:
        return
    raise PaperCandidateStepError(
        f"partial category-shard output exists but is not complete: {root}"
    )


def run_step(
    plan: dict[str, Any],
    *,
    selector: str,
    category: str | None = None,
    output_root: Path | None = None,
    dry_run: bool = False,
    stream_length: int | None = None,
    command_runner: CommandRunner = run_p0_full_step._default_command_runner,
) -> tuple[int, dict[str, Any]]:
    _configure_full_step_module(plan)
    index, step = run_p0_full_step.resolve_step(plan, selector)
    if step.get("candidate_scope") == "category_shard":
        if category is None:
            raise PaperCandidateStepError("--category is required for category-shard execution")
        if step.get("category") is not None:
            if step.get("category") != category:
                raise PaperCandidateStepError(
                    f"selected shard category {step.get('category')!r} != {category!r}"
                )
            if output_root is not None and _as_posix(output_root) != _as_posix(
                step["output_root"]
            ):
                raise PaperCandidateStepError(
                    "requested output root does not match selected category shard: "
                    f"{output_root} != {step['output_root']}"
                )
        else:
            step = prepare_category_shard_step(step, category=category, output_root=output_root)
        output_root = Path(str(step["output_root"]))
    if stream_length is None:
        stream_length = int(
            step.get("paper_candidate_stream_length")
            or plan.get("paper_candidate_stream_length")
            or 64
        )
    if stream_length <= 20:
        raise PaperCandidateStepError("paper-candidate stream_length must be > 20")
    run_p0_full_step.validate_step_contract(step, output_root=output_root)

    if dry_run:
        print(
            f"[{index}] DRY-RUN paper-candidate step {step.get('step_id')}: "
            f"category={step.get('category')} output_root={step.get('output_root')} "
            f"stream_length={stream_length}"
        )
        return index, step

    _raise_on_partial_outputs(step)
    if _outputs_exist(step):
        verify_completed_step(step)
        print(
            f"[{index}] SKIP complete paper-candidate step {step.get('step_id')}: "
            f"category={step.get('category')}"
        )
        return index, step

    local_plan = dict(plan)
    local_plan["steps"] = [step]
    _, selected = run_p0_full_step.run_step(
        local_plan,
        selector=step["step_id"],
        output_root=output_root,
        stream_length=stream_length,
        command_runner=command_runner,
    )
    _patch_manifest_status(selected, stream_length=stream_length)
    verify_completed_step(selected)
    print(
        f"[{index}] COMPLETE paper-candidate step {selected.get('step_id')}: "
        "execution_mode=production"
    )
    return index, selected


def verify_completed_step(step: dict[str, Any]) -> None:
    _configure_full_step_module({"patchcore_sampler_percentage": step.get("patchcore_sampler_percentage", 0.1)})
    run_p0_full_step.verify_completed_step(step, completion_mode="production")
    metrics_path = Path(str(step["outputs"]["aggregate_metrics"]))
    with metrics_path.open(newline="") as handle:
        statuses = {row.get("status") for row in csv.DictReader(handle)}
    if statuses != {"measured_paper_candidate"}:
        raise PaperCandidateStepError(
            f"paper-candidate metrics status must be measured_paper_candidate, got {statuses}"
        )
    manifest = _load_json(Path(str(step["outputs"]["aggregate_manifest"])))
    _enforce_metadata(manifest, context="aggregate manifest")
    if manifest.get("execution_mode") != "production":
        raise PaperCandidateStepError("aggregate manifest execution_mode must be production")
    if manifest.get("status") != "measured_paper_candidate_production_complete":
        raise PaperCandidateStepError("aggregate manifest is not paper-candidate complete")
    if step.get("candidate_scope") == "category_shard":
        category = step.get("category")
        if manifest.get("candidate_scope") != "category_shard":
            raise PaperCandidateStepError("category shard manifest candidate_scope mismatch")
        if manifest.get("category") != category:
            raise PaperCandidateStepError(
                f"category shard manifest category {manifest.get('category')!r} != {category!r}"
            )
        if manifest.get("category_count") != 1:
            raise PaperCandidateStepError("category shard manifest category_count must be 1")
        if manifest.get("stream_length") != step.get("paper_candidate_stream_length"):
            raise PaperCandidateStepError("category shard stream_length metadata mismatch")
        if _normalized_seeds(manifest.get("seeds")) != _normalized_seeds(step.get("seeds")):
            raise PaperCandidateStepError("category shard seeds metadata mismatch")


def verify_full_category_candidate(step: dict[str, Any]) -> None:
    """Fail unless a paper-candidate output is a full-category result."""
    verify_completed_step(step)
    manifest = _load_json(Path(str(step["outputs"]["aggregate_manifest"])))
    if manifest.get("candidate_scope") != "full_category":
        raise PaperCandidateStepError(
            f"not a full-category paper candidate: {manifest.get('candidate_scope')}"
        )
    if manifest.get("category_count") != manifest.get("full_p0_category_count"):
        raise PaperCandidateStepError("paper candidate does not cover all declared categories")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--step", help="Paper-candidate step id or zero-based index")
    selector.add_argument("--step-id", help="Paper-candidate step id")
    selector.add_argument("--index", type=int, help="Zero-based paper-candidate step index")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--category", help="Required category for category-shard execution")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stream-length", type=int)
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
            category=args.category,
            output_root=args.output_root,
            dry_run=args.dry_run,
            stream_length=args.stream_length,
            command_runner=run_p0_full_step._default_command_runner,
        )
    except (
        json.JSONDecodeError,
        OSError,
        PaperCandidateStepError,
        run_p0_full_step.FullP0StepError,
    ) as error:
        raise SystemExit(f"ERROR: {error}") from error

    print(
        "selected_step="
        f"{index} step_id={step.get('step_id')} run_tier=paper_candidate "
        "paper_allowed=false claim_allowed=false review_status=review_pending"
    )


if __name__ == "__main__":
    main()
