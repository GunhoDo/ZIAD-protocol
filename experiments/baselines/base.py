"""Shared baseline wrapper interface."""
from abc import ABC, abstractmethod


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
