"""Online Prototype-EMA diagnostic detector.

This baseline is a lightweight stream-updating detector for protocol diagnosis.
It extracts deterministic image descriptors, scores each item by distance to
the previous online prototype, then updates that prototype with EMA. Unlike the
frozen baselines and post-hoc score wrappers, the detector state changes during
stream traversal, so matched i.i.d./bursty streams can produce different scores.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

from PIL import Image

from .base import BaselineWrapper, validate_execution_contract

BASELINE_NAME = "OnlinePrototypeEMA"
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


def _descriptor(path: Path, *, size: int) -> list[float]:
    with Image.open(path) as image:
        gray = image.convert("L").resize((size, size))
        pixels = [value / 255.0 for value in gray.getdata()]
    mean = statistics.fmean(pixels)
    variance = statistics.fmean((value - mean) ** 2 for value in pixels)
    contrast = variance**0.5
    # Include both global and coarse spatial statistics. The normalization keeps
    # the global terms on the same rough scale as individual pixel bins.
    return pixels + [mean, contrast]


def _l2(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)) / len(left))


class OnlinePrototypeEMAWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        validate_execution_contract(
            config,
            baseline_name=BASELINE_NAME,
            supported_memory_policies={"Prototype-EMA"},
            supported_calibrations={"none"},
        )
        stream_items = _load_stream_items(stream_path)
        alpha = _cfg(config, "prototype_ema_alpha", 0.08, float)
        image_size = _cfg(config, "descriptor_size", 16, int)
        if not 0.0 < alpha <= 1.0:
            raise RuntimeError("OnlinePrototypeEMA prototype_ema_alpha must be in (0, 1].")
        if image_size < 4:
            raise RuntimeError("OnlinePrototypeEMA descriptor_size must be >= 4.")

        prototype: list[float] | None = None
        rows: list[dict[str, Any]] = []
        for item in stream_items:
            start = time.perf_counter()
            image_path = _resolve_stream_image_path(str(item["image_path"]), dataset_root)
            feature = _descriptor(image_path, size=image_size)
            if prototype is None:
                score = 0.0
                prototype = list(feature)
            else:
                score = _l2(feature, prototype)
                prototype = [
                    (1.0 - alpha) * old + alpha * new
                    for old, new in zip(prototype, feature)
                ]
            latency_ms = (time.perf_counter() - start) * 1000.0
            rows.append(
                {
                    "stream_index": item["stream_index"],
                    "image_path": item["image_path"],
                    "label": item["label"],
                    "category": item["category"],
                    "anomaly_score": f"{score:.10f}",
                    "latency_ms": f"{latency_ms:.6f}",
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
    OnlinePrototypeEMAWrapper().run(stream_path, dataset_root, output_csv, config)
