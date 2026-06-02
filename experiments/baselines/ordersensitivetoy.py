"""Order-sensitive diagnostic baseline for ZIAD protocol checks.

This wrapper is intentionally simple and deterministic. It computes a cheap
image-derived raw score, then mixes the current raw score with a sliding window
of previous raw scores. The goal is not to propose a competitive detector; it
is to provide a controlled order-sensitive baseline that exercises the ZIAD
stream-order machinery without using labels or hand-written metric values.
"""
from __future__ import annotations

import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any

from PIL import Image

from .base import BaselineWrapper, validate_execution_contract

BASELINE_NAME = "OrderSensitiveToy"
SCORE_FIELDS = [
    "stream_index",
    "image_path",
    "label",
    "category",
    "anomaly_score",
    "latency_ms",
    "peak_vram_mb",
    "status",
]
REQUIRED_STREAM_ITEM_FIELDS = {
    "stream_index",
    "image_path",
    "label",
    "category",
    "source_split",
    "anomaly_type",
}


def _cfg(config: dict[str, Any], key: str, default: Any, cast: Any = None) -> Any:
    value = config.get(key, default)
    if cast is None or value is None:
        return value
    if cast is bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return cast(value)


def _load_stream_items(stream_path: str) -> list[dict[str, Any]]:
    path = Path(stream_path)
    if not path.exists():
        raise RuntimeError(f"Stream file is required but missing: {stream_path}")
    payload = json.loads(path.read_text())
    items = payload.get("items") or []
    if not items:
        raise RuntimeError(f"Stream file has no items: {stream_path}")

    validated: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("Stream items must be objects.")
        missing = sorted(REQUIRED_STREAM_ITEM_FIELDS - set(item))
        if missing:
            raise RuntimeError(f"Stream item missing required field(s): {missing}")
        copy = dict(item)
        copy["stream_index"] = int(copy["stream_index"])
        copy["label"] = int(copy["label"])
        if copy["label"] not in {0, 1}:
            raise RuntimeError(f"Stream labels must be binary 0/1: {copy['label']!r}")
        validated.append(copy)

    indices = [item["stream_index"] for item in validated]
    if sorted(indices) != list(range(len(validated))):
        raise RuntimeError("Stream item stream_index values must be contiguous from 0.")
    return sorted(validated, key=lambda item: item["stream_index"])


def _ensure_inside_dataset(path: Path, dataset_root: Path) -> Path:
    root = dataset_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise RuntimeError(f"Stream image path resolves outside dataset_root: {path}") from error
    return resolved


def _resolve_stream_image_path(image_path: str, dataset_root: str | Path) -> Path:
    root = Path(dataset_root)
    candidate = Path(image_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = _ensure_inside_dataset(candidate, root)
    if not resolved.is_file():
        raise RuntimeError(f"Stream references missing image: {image_path}")
    return resolved


def _raw_image_score(path: Path) -> float:
    with Image.open(path) as image:
        gray = image.convert("L").resize((32, 32))
        pixels = [value / 255.0 for value in gray.getdata()]
    mean = statistics.fmean(pixels)
    variance = statistics.fmean((value - mean) ** 2 for value in pixels)
    contrast = variance**0.5
    return mean + 0.5 * contrast


class OrderSensitiveToyWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        validate_execution_contract(
            config,
            baseline_name=BASELINE_NAME,
            supported_memory_policies={"sliding_window"},
            supported_calibrations={"none"},
        )
        stream_items = _load_stream_items(stream_path)
        window = _cfg(config, "window_size", 5, int)
        alpha = _cfg(config, "current_score_weight", 0.35, float)
        if window < 1:
            raise RuntimeError("OrderSensitiveToy window_size must be >= 1")
        if alpha < 0.0 or alpha > 1.0:
            raise RuntimeError("OrderSensitiveToy current_score_weight must be in [0, 1]")

        previous: list[float] = []
        rows: list[dict[str, Any]] = []
        for item in stream_items:
            start = time.perf_counter()
            image_path = _resolve_stream_image_path(str(item["image_path"]), dataset_root)
            raw_score = _raw_image_score(image_path)
            if previous:
                history = previous[-window:]
                history_score = statistics.fmean(history)
            else:
                history_score = raw_score
            score = alpha * raw_score + (1.0 - alpha) * history_score
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            previous.append(raw_score)
            rows.append(
                {
                    "stream_index": item["stream_index"],
                    "image_path": item["image_path"],
                    "label": item["label"],
                    "category": item["category"],
                    "anomaly_score": f"{score:.10f}",
                    "latency_ms": f"{elapsed_ms:.6f}",
                    "peak_vram_mb": "0",
                    "status": "measured",
                }
            )

        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    OrderSensitiveToyWrapper().run(stream_path, dataset_root, output_csv, config)
