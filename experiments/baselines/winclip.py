"""WinCLIP baseline wrapper.

This wrapper runs the local WinCLIP implementation in zero-shot mode on the
project stream JSON and writes the common score CSV schema.  It deliberately
does not call the upstream dataset loader because that loader hard-codes a
dataset path outside this repository and evaluates the full test split.  The
stream file remains the source of truth for image order and membership.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .base import BaselineWrapper, _setup_error

BASELINE_NAME = "WinCLIP"
LOCAL_PATH = "external/WinClip"
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
    env_key = "WINCLIP_" + key.upper()
    value = config.get(key, os.environ.get(env_key, default))
    if cast is None or value is None:
        return value
    if cast is bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return cast(value)


def _csv_ints(value: Any, default: tuple[int, ...]) -> tuple[int, ...]:
    if value is None or value == "":
        return tuple(default)
    if isinstance(value, str):
        return tuple(int(item.strip()) for item in value.split(",") if item.strip())
    return tuple(int(item) for item in value)


def _ensure_winclip_importable() -> None:
    root = Path(LOCAL_PATH).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _dependency_error(error: ImportError) -> RuntimeError:
    return RuntimeError(
        "WinCLIP dependency import failed. Install the local WinCLIP runtime "
        "dependencies before running the wrapper, e.g.\n"
        "  python3 -m pip install open_clip_torch==2.23.0 ftfy\n"
        "Original import error: "
        f"{error}"
    )


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
            raise RuntimeError("Stream items must be objects with required metadata fields.")
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
        raise RuntimeError(
            f"Stream image path resolves outside dataset_root: {path}"
        ) from error
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


def _image_score(anomaly_map: Any) -> float:
    array = np.asarray(anomaly_map, dtype=np.float32)
    if array.size == 0:
        raise RuntimeError("WinCLIP produced an empty anomaly map.")
    return float(array.max())


class WinCLIPWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        if not os.path.isdir(LOCAL_PATH):
            raise _setup_error(BASELINE_NAME, LOCAL_PATH)

        _ensure_winclip_importable()
        try:
            import torch
            from WinCLIP import WinClipAD
        except ImportError as error:  # pragma: no cover - environment-dependent
            raise _dependency_error(error) from error

        category = str(config.get("category") or _cfg(config, "category", "bottle"))
        if not (Path(dataset_root) / category).is_dir():
            raise RuntimeError(f"MVTec category not found: {Path(dataset_root) / category}")

        stream_items = _load_stream_items(stream_path)
        batch_size = _cfg(config, "batch_size", 2, int)
        img_resize = _cfg(config, "img_resize", 240, int)
        img_cropsize = _cfg(config, "img_cropsize", 240, int)
        resolution = _cfg(config, "resolution", 400, int)
        backbone = str(_cfg(config, "backbone", "ViT-B-16-plus-240"))
        pretrained_dataset = str(_cfg(config, "pretrained_dataset", "laion400m_e32"))
        scales = _csv_ints(_cfg(config, "scales", None), (2, 3))
        force_cpu = _cfg(config, "use_cpu", not torch.cuda.is_available(), bool)
        device = torch.device("cpu" if force_cpu or not torch.cuda.is_available() else "cuda:0")

        model = WinClipAD(
            out_size_h=resolution,
            out_size_w=resolution,
            device=str(device),
            backbone=backbone,
            pretrained_dataset=pretrained_dataset,
            scales=scales,
            img_resize=img_resize,
            img_cropsize=img_cropsize,
        ).to(device)
        # The upstream class hard-codes fp16 for lower GPU memory.  CPU smoke
        # runs need fp32 kernels, and using fp32 is also safer for reproducible
        # local CI on machines without CUDA.
        if device.type == "cpu":
            model.precision = "fp32"
            model.model.float()
        model.eval_mode()
        model.build_text_feature_gallery(category)

        rows = self._predict_rows(
            model=model,
            stream_items=stream_items,
            dataset_root=dataset_root,
            category=category,
            batch_size=batch_size,
            device=device,
            torch=torch,
        )

        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _predict_rows(
        *,
        model: Any,
        stream_items: list[dict[str, Any]],
        dataset_root: str | Path,
        category: str,
        batch_size: int,
        device: Any,
        torch: Any,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for offset in range(0, len(stream_items), batch_size):
            batch_items = stream_items[offset : offset + batch_size]
            pil_images = [
                Image.open(_resolve_stream_image_path(str(item["image_path"]), dataset_root)).convert("RGB")
                for item in batch_items
            ]
            batch = torch.stack([model.transform(image) for image in pil_images], dim=0).to(device)

            if device.type == "cuda":
                torch.cuda.synchronize(device)
                torch.cuda.reset_peak_memory_stats(device)
            start = time.perf_counter()
            with torch.no_grad():
                anomaly_maps = model(batch)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
                peak_vram_mb = torch.cuda.max_memory_allocated(device) / (1024 * 1024)
            else:
                peak_vram_mb = 0.0
            latency_ms = (time.perf_counter() - start) * 1000 / max(len(batch_items), 1)

            for item, anomaly_map in zip(batch_items, anomaly_maps):
                rows.append(
                    {
                        "stream_index": item["stream_index"],
                        "image_path": str(item["image_path"]),
                        "label": int(item["label"]),
                        "category": str(item.get("category", category)),
                        "anomaly_score": f"{_image_score(anomaly_map):.10f}",
                        "latency_ms": f"{latency_ms:.4f}",
                        "peak_vram_mb": f"{peak_vram_mb:.2f}",
                        "status": "measured",
                    }
                )
        return rows


def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    WinCLIPWrapper().run(stream_path, dataset_root, output_csv, config)
