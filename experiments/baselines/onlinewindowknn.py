"""Online FIFO-window kNN diagnostic detector.

This baseline is a lightweight true-online detector for stream-order protocol
diagnosis. It extracts the same deterministic image descriptor used by
OnlinePrototypeEMA, scores the current item against a FIFO memory bank before
updating that bank, then inserts the current feature. Because each score
depends on the previous stream prefix, matched i.i.d. and bursty streams can
produce different future scores without any post-hoc score manipulation.
"""
from __future__ import annotations

import csv
import math
import time
from pathlib import Path
from typing import Any, Iterable

from .base import BaselineWrapper, validate_execution_contract
from .onlineprototypeema import (
    REQUIRED_STREAM_ITEM_FIELDS,
    SCORE_FIELDS,
    _cfg,
    _descriptor,
    _load_stream_items,
    _resolve_stream_image_path,
)

BASELINE_NAME = "OnlineWindowKNN"


def _l2(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)) / len(left))


def _cosine_distance(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 1.0
    similarity = sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)
    return 1.0 - max(-1.0, min(1.0, similarity))


def _distance(left: list[float], right: list[float], metric: str) -> float:
    if metric == "l2":
        return _l2(left, right)
    if metric == "cosine":
        return _cosine_distance(left, right)
    raise RuntimeError("OnlineWindowKNN distance_metric must be l2 or cosine.")


def score_against_memory(
    feature: list[float],
    memory: Iterable[list[float]],
    *,
    metric: str = "l2",
    startup_score: float = 0.0,
) -> float:
    """Return nearest-neighbor distance to the current memory bank."""
    bank = list(memory)
    if not bank:
        return startup_score
    return min(_distance(feature, candidate, metric) for candidate in bank)


def fifo_update(memory: list[list[float]], feature: list[float], *, max_size: int) -> None:
    """Append feature and evict the oldest item when the FIFO bank exceeds K."""
    if max_size <= 0:
        raise RuntimeError("OnlineWindowKNN memory_size must be positive.")
    memory.append(list(feature))
    while len(memory) > max_size:
        del memory[0]


class OnlineWindowKNNWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        validate_execution_contract(
            config,
            baseline_name=BASELINE_NAME,
            supported_memory_policies={"FIFO"},
            supported_calibrations={"none"},
        )
        stream_items = _load_stream_items(stream_path)
        memory_size = _cfg(config, "memory_size", 16, int)
        image_size = _cfg(config, "descriptor_size", 16, int)
        metric = str(config.get("distance_metric", "l2")).strip().lower()
        startup_score = _cfg(config, "startup_score", 0.0, float)
        if memory_size <= 0:
            raise RuntimeError("OnlineWindowKNN memory_size must be positive.")
        if image_size < 4:
            raise RuntimeError("OnlineWindowKNN descriptor_size must be >= 4.")
        if metric not in {"l2", "cosine"}:
            raise RuntimeError("OnlineWindowKNN distance_metric must be l2 or cosine.")

        memory: list[list[float]] = []
        rows: list[dict[str, Any]] = []
        for item in stream_items:
            start = time.perf_counter()
            image_path = _resolve_stream_image_path(str(item["image_path"]), dataset_root)
            feature = _descriptor(image_path, size=image_size)
            score = score_against_memory(
                feature,
                memory,
                metric=metric,
                startup_score=startup_score,
            )
            fifo_update(memory, feature, max_size=memory_size)
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
    OnlineWindowKNNWrapper().run(stream_path, dataset_root, output_csv, config)
