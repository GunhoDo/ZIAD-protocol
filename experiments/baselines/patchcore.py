"""PatchCore baseline wrapper stub."""
import os
from .base import BaselineWrapper, _setup_error

BASELINE_NAME = "PatchCore"
LOCAL_PATH = "external/PatchCore"


class PatchCoreWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        if not os.path.isdir(LOCAL_PATH):
            raise _setup_error(BASELINE_NAME, LOCAL_PATH)
        raise RuntimeError(
            f"{BASELINE_NAME} clone found at {LOCAL_PATH} but integration is not yet implemented. "
            "Implement this wrapper before running first success gate A."
        )


def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    PatchCoreWrapper().run(stream_path, dataset_root, output_csv, config)
