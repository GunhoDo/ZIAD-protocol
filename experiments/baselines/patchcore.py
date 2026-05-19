"""PatchCore baseline wrapper.

This wrapper runs the upstream amazon-science/patchcore-inspection implementation
against one MVTec AD category and writes the project-wide score CSV schema.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .base import BaselineWrapper, _setup_error

BASELINE_NAME = "PatchCore"
LOCAL_PATH = "external/patchcore-inspection"
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


def _cfg(config: dict[str, Any], key: str, default: Any, cast: Any = None) -> Any:
    """Read a PatchCore option from config, env, or a default."""
    env_key = "PATCHCORE_" + key.upper()
    value = config.get(key, os.environ.get(env_key, default))
    if cast is None or value is None:
        return value
    if cast is bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return cast(value)


def _csv_list(value: Any, default: Iterable[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def _patchcore_src() -> Path:
    return Path(LOCAL_PATH) / "src"


def _ensure_patchcore_importable() -> None:
    src = _patchcore_src().resolve()
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _dependency_error(error: ImportError) -> RuntimeError:
    return RuntimeError(
        "PatchCore dependency import failed. Install the upstream requirements before "
        "running the wrapper. The upstream requirements file omits timm, which "
        "backbones.py imports, so install both, e.g.\n"
        f"  python3 -m pip install -r {LOCAL_PATH}/requirements.txt timm\n"
        f"Original import error: {error}"
    )


def _relative_path(path: str) -> str:
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(candidate)


def _score_to_float(score: Any) -> float:
    return float(np.asarray(score).reshape(-1)[0])


def _load_stream_order(stream_path: str) -> list[str]:
    """Return optional ordered image paths from a stream JSON file.

    Placeholder streams have empty `items`; in that case the wrapper evaluates
    the full category test split in the upstream dataset order.
    """
    path = Path(stream_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    items = payload.get("items") or []
    ordered: list[str] = []
    for item in items:
        if isinstance(item, str):
            ordered.append(item)
        elif isinstance(item, dict):
            image_path = item.get("image_path") or item.get("path") or item.get("file")
            if image_path:
                ordered.append(str(image_path))
    return ordered


def _apply_stream_order(rows: list[dict[str, Any]], stream_path: str) -> list[dict[str, Any]]:
    ordered_paths = _load_stream_order(stream_path)
    if not ordered_paths:
        return rows

    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        rel = str(row["image_path"])
        by_key[rel] = row
        by_key[str(Path(rel).resolve())] = row

    ordered_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for image_path in ordered_paths:
        keys = [image_path, _relative_path(image_path), str(Path(image_path).resolve())]
        row = next((by_key[key] for key in keys if key in by_key), None)
        if row is None:
            missing.append(image_path)
            continue
        ordered_rows.append(dict(row))

    if missing:
        raise RuntimeError(
            "Stream references image(s) outside the evaluated PatchCore split: "
            + ", ".join(missing[:5])
            + (" ..." if len(missing) > 5 else "")
        )
    return ordered_rows


class PatchCoreWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        if not os.path.isdir(LOCAL_PATH):
            raise _setup_error(BASELINE_NAME, LOCAL_PATH)

        _ensure_patchcore_importable()
        try:
            import torch
            import patchcore.backbones
            import patchcore.common
            import patchcore.patchcore
            import patchcore.sampler
            import patchcore.utils
            from patchcore.datasets.mvtec import DatasetSplit, MVTecDataset
        except ImportError as error:  # pragma: no cover - environment-dependent
            raise _dependency_error(error) from error

        category = str(config.get("category") or _cfg(config, "category", "bottle"))
        seed = _cfg(config, "seed", 0, int)
        resize = _cfg(config, "resize", 256, int)
        imagesize = _cfg(config, "imagesize", 224, int)
        batch_size = _cfg(config, "batch_size", 2, int)
        num_workers = _cfg(config, "num_workers", 0, int)
        backbone_name = str(_cfg(config, "backbone", "wideresnet50"))
        layers = _csv_list(_cfg(config, "layers", None), ["layer2", "layer3"])
        sampler_name = str(_cfg(config, "sampler", "approx_greedy_coreset"))
        sampler_percentage = _cfg(config, "sampler_percentage", 0.1, float)
        pretrain_embed_dimension = _cfg(config, "pretrain_embed_dimension", 1024, int)
        target_embed_dimension = _cfg(config, "target_embed_dimension", 1024, int)
        anomaly_scorer_num_nn = _cfg(config, "anomaly_scorer_num_nn", 1, int)
        patchsize = _cfg(config, "patchsize", 3, int)
        faiss_on_gpu = _cfg(config, "faiss_on_gpu", False, bool)
        faiss_num_workers = _cfg(config, "faiss_num_workers", 8, int)
        max_test_images_raw = _cfg(config, "max_test_images", None)
        max_test_images = (
            int(max_test_images_raw) if max_test_images_raw not in {None, ""} else None
        )

        if not (Path(dataset_root) / category).is_dir():
            raise RuntimeError(f"MVTec category not found: {Path(dataset_root) / category}")

        gpu = str(_cfg(config, "gpu", "0" if torch.cuda.is_available() else ""))
        device = torch.device(f"cuda:{gpu}" if gpu != "" and torch.cuda.is_available() else "cpu")
        patchcore.utils.fix_seeds(seed, device)

        train_dataset = MVTecDataset(
            dataset_root,
            classname=category,
            resize=resize,
            imagesize=imagesize,
            split=DatasetSplit.TRAIN,
            seed=seed,
        )
        test_dataset = MVTecDataset(
            dataset_root,
            classname=category,
            resize=resize,
            imagesize=imagesize,
            split=DatasetSplit.TEST,
            seed=seed,
        )
        if len(train_dataset) == 0 or len(test_dataset) == 0:
            raise RuntimeError(
                f"PatchCore requires non-empty train/test splits for {dataset_root}/{category}."
            )

        train_loader = torch.utils.data.DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=device.type == "cuda",
        )
        test_loader = torch.utils.data.DataLoader(
            test_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=device.type == "cuda",
        )

        sampler = self._make_sampler(patchcore.sampler, sampler_name, sampler_percentage, device)
        nn_method = patchcore.common.FaissNN(faiss_on_gpu, faiss_num_workers)
        backbone = patchcore.backbones.load(backbone_name)
        backbone.name = backbone_name
        backbone.seed = None

        model = patchcore.patchcore.PatchCore(device)
        model.load(
            backbone=backbone,
            layers_to_extract_from=layers,
            device=device,
            input_shape=train_dataset.imagesize,
            pretrain_embed_dimension=pretrain_embed_dimension,
            target_embed_dimension=target_embed_dimension,
            patchsize=patchsize,
            featuresampler=sampler,
            anomaly_scorer_num_nn=anomaly_scorer_num_nn,
            nn_method=nn_method,
        )

        if device.type == "cuda":
            torch.cuda.empty_cache()
        model.fit(train_loader)

        rows = self._predict_rows(
            model=model,
            test_loader=test_loader,
            category=category,
            device=device,
            max_test_images=max_test_images,
            torch=torch,
        )
        rows = _apply_stream_order(rows, stream_path)
        for idx, row in enumerate(rows):
            row["stream_index"] = idx

        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _make_sampler(sampler_module: Any, name: str, percentage: float, device: Any) -> Any:
        if name == "identity":
            return sampler_module.IdentitySampler()
        if name == "greedy_coreset":
            return sampler_module.GreedyCoresetSampler(percentage, device)
        if name == "approx_greedy_coreset":
            return sampler_module.ApproximateGreedyCoresetSampler(percentage, device)
        if name == "random":
            return sampler_module.RandomSampler(percentage)
        raise RuntimeError(f"Unsupported PatchCore sampler: {name}")

    @staticmethod
    def _predict_rows(
        model: Any,
        test_loader: Any,
        category: str,
        device: Any,
        max_test_images: int | None,
        torch: Any,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for batch in test_loader:
            image_paths = list(batch["image_path"])
            labels = [int(x) for x in batch["is_anomaly"].numpy().tolist()]
            images = batch["image"]

            if max_test_images is not None:
                remaining = max_test_images - len(rows)
                if remaining <= 0:
                    break
                image_paths = image_paths[:remaining]
                labels = labels[:remaining]
                images = images[:remaining]

            if device.type == "cuda":
                torch.cuda.synchronize(device)
                torch.cuda.reset_peak_memory_stats(device)
            start = time.perf_counter()
            scores, _masks = model._predict(images)  # Upstream batch-level inference.
            if device.type == "cuda":
                torch.cuda.synchronize(device)
                peak_vram_mb = torch.cuda.max_memory_allocated(device) / (1024 * 1024)
            else:
                peak_vram_mb = 0.0
            latency_ms = (time.perf_counter() - start) * 1000 / max(len(scores), 1)

            for image_path, label, score in zip(image_paths, labels, scores):
                rows.append(
                    {
                        "stream_index": len(rows),
                        "image_path": _relative_path(image_path),
                        "label": label,
                        "category": category,
                        "anomaly_score": f"{_score_to_float(score):.10f}",
                        "latency_ms": f"{latency_ms:.4f}",
                        "peak_vram_mb": f"{peak_vram_mb:.2f}",
                        "status": "measured",
                    }
                )
        return rows


def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    PatchCoreWrapper().run(stream_path, dataset_root, output_csv, config)
