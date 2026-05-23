"""Shared baseline wrapper interface."""
from abc import ABC, abstractmethod
from typing import Any


class BaselineWrapper(ABC):
    """Abstract interface every baseline wrapper must implement."""

    @abstractmethod
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        """Write common score CSV rows or raise RuntimeError if not configured."""
        raise NotImplementedError


def _setup_error(baseline_name: str, local_path: str) -> RuntimeError:
    return RuntimeError(
        f"{baseline_name} is not configured.\n"
        f"Expected clone at: {local_path}\n"
        f"Repo URL and commit hash are TBD — see experiments/configs/baselines.yaml.\n"
        f"Run 'bash scripts/setup_baselines.sh' for clone instructions."
    )


def validate_execution_contract(
    config: dict[str, Any],
    *,
    baseline_name: str,
    supported_memory_policies: set[str] | None = None,
    supported_calibrations: set[str] | None = None,
) -> tuple[str, str]:
    """Validate P0 execution dimensions before a wrapper can run.

    The current wrappers only implement their default smoke behavior. Rejecting
    unsupported memory policies and calibration modes here prevents a P0 shard
    from silently falling back to default/SCS or uncalibrated scores.
    """
    supported_memory_policies = supported_memory_policies or {"default/SCS"}
    supported_calibrations = supported_calibrations or {"none"}
    memory_policy = str(config.get("memory_policy", "default/SCS"))
    calibration = str(config.get("calibration", "none"))

    if memory_policy not in supported_memory_policies:
        supported = ", ".join(sorted(supported_memory_policies))
        raise RuntimeError(
            f"{baseline_name} does not support memory_policy={memory_policy!r}. "
            f"Supported memory_policy value(s): {supported}. "
            "Do not silently substitute default/SCS for P0 runs."
        )
    if calibration not in supported_calibrations:
        supported = ", ".join(sorted(supported_calibrations))
        raise RuntimeError(
            f"{baseline_name} does not support calibration={calibration!r}. "
            f"Supported calibration value(s): {supported}. "
            "Do not silently substitute uncalibrated scores for P0 runs."
        )
    return memory_policy, calibration
