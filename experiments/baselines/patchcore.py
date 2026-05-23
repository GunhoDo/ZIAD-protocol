"""PatchCore baseline wrapper.

This wrapper runs the upstream amazon-science/patchcore-inspection implementation
against one MVTec AD category and writes the project-wide score CSV schema.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .base import BaselineWrapper, _setup_error, validate_execution_contract

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


def _cache_key(parts: dict[str, Any]) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _valid_patchcore_cache(path: Path) -> bool:
    return (
        (path / "patchcore_params.pkl").is_file()
        and (path / "nnscorer_search_index.faiss").is_file()
    )


def _score_cache_path(model_cache_dir: Path) -> Path:
    return model_cache_dir / "image_scores.json"


def _load_score_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("rows", {})
    return rows if isinstance(rows, dict) else {}


def _write_score_cache(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class _FIFOSampler:
    """Keep the newest features after oldest-first eviction."""

    def __init__(self, percentage: float):
        if not 0 < percentage <= 1:
            raise ValueError("FIFO percentage value must be in (0, 1].")
        self.percentage = percentage

    def run(self, features: Any) -> Any:
        if len(features) == 0 or self.percentage == 1:
            return features
        sample_count = max(1, int(len(features) * self.percentage))
        return features[-sample_count:]


REQUIRED_STREAM_ITEM_FIELDS = {
    "stream_index",
    "image_path",
    "label",
    "category",
    "source_split",
    "anomaly_type",
}


def _load_stream_items(stream_path: str, *, required: bool = False) -> list[dict[str, Any]]:
    """Return validated stream items from a stream JSON file.

    Missing or empty stream files preserve the legacy full-test-split behavior.
    Non-empty streams are strict because they are now part of the experiment
    contract: each item must carry label/category/source metadata and contiguous
    ``stream_index`` values.
    """
    path = Path(stream_path)
    if not path.exists():
        if required:
            raise RuntimeError(f"Stream file is required but missing: {stream_path}")
        return []
    payload = json.loads(path.read_text())
    items = payload.get("items") or []
    if not items:
        if required:
            raise RuntimeError(f"Stream file has no items: {stream_path}")
        return []
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


def _row_resolved_path(row: dict[str, Any]) -> Path:
    row_path = Path(str(row["image_path"]))
    if not row_path.is_absolute():
        row_path = Path.cwd() / row_path
    return row_path.resolve()


def _apply_stream_order(
    rows: list[dict[str, Any]],
    stream_path: str,
    dataset_root: str | Path = ".",
    *,
    require_stream: bool = False,
) -> list[dict[str, Any]]:
    stream_items = _load_stream_items(stream_path, required=require_stream)
    if not stream_items:
        return rows

    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_key[str(_row_resolved_path(row))] = row

    ordered_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in stream_items:
        image_path = str(item["image_path"])
        resolved = _resolve_stream_image_path(image_path, dataset_root)
        row = by_key.get(str(resolved))
        if row is None:
            missing.append(image_path)
            continue
        if int(row.get("label", item["label"])) != int(item["label"]):
            raise RuntimeError(
                "Stream label mismatch for "
                f"{image_path}: stream={item['label']} row={row.get('label')}"
            )
        ordered = dict(row)
        ordered["stream_index"] = item["stream_index"]
        ordered["image_path"] = image_path
        ordered["label"] = int(item["label"])
        ordered["category"] = str(item["category"])
        ordered_rows.append(ordered)

    if missing:
        raise RuntimeError(
            "Stream references image(s) outside the evaluated PatchCore split: "
            + ", ".join(missing[:5])
            + (" ..." if len(missing) > 5 else "")
        )
    if len(ordered_rows) != len(stream_items):
        raise RuntimeError(
            "PatchCore stream filtering did not produce exactly one row per stream item."
        )
    return ordered_rows


def _rows_from_score_cache(
    score_cache: dict[str, dict[str, Any]],
    stream_items: list[dict[str, Any]],
    dataset_root: str | Path,
) -> list[dict[str, Any]] | None:
    rows: list[dict[str, Any]] = []
    for item in stream_items:
        resolved = _resolve_stream_image_path(str(item["image_path"]), dataset_root)
        cached = score_cache.get(str(resolved))
        if cached is None:
            return None
        if int(cached.get("label", item["label"])) != int(item["label"]):
            raise RuntimeError(
                "Cached PatchCore label mismatch for "
                f"{item['image_path']}: stream={item['label']} cache={cached.get('label')}"
            )
        row = dict(cached)
        row["stream_index"] = int(item["stream_index"])
        row["image_path"] = str(item["image_path"])
        row["label"] = int(item["label"])
        row["category"] = str(item["category"])
        row["status"] = "measured"
        rows.append(row)
    return rows


def _merge_rows_into_score_cache(
    score_cache: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    dataset_root: str | Path,
) -> dict[str, dict[str, Any]]:
    merged = dict(score_cache)
    for row in rows:
        resolved = _resolve_stream_image_path(str(row["image_path"]), dataset_root)
        cached = dict(row)
        cached.pop("stream_index", None)
        cached["image_path"] = str(resolved)
        cached["label"] = int(cached["label"])
        cached["status"] = "measured"
        merged[str(resolved)] = cached
    return merged


def _filter_test_dataset_to_stream(
    test_dataset: Any,
    stream_items: list[dict[str, Any]],
    dataset_root: str | Path,
) -> None:
    """Restrict the upstream MVTec test dataset to stream-referenced images."""
    by_path = {
        str(Path(entry[2]).resolve()): entry for entry in test_dataset.data_to_iterate
    }
    selected: list[Any] = []
    missing: list[str] = []
    for item in stream_items:
        image_path = str(item["image_path"])
        resolved = _resolve_stream_image_path(image_path, dataset_root)
        entry = by_path.get(str(resolved))
        if entry is None:
            missing.append(image_path)
            continue
        anomaly_name = str(entry[1])
        expected_label = 0 if anomaly_name == "good" else 1
        if expected_label != int(item["label"]):
            raise RuntimeError(
                "Stream label mismatch for "
                f"{image_path}: stream={item['label']} dataset={expected_label}"
            )
        selected.append(entry)

    if missing:
        raise RuntimeError(
            "Stream references image(s) outside the PatchCore test split: "
            + ", ".join(missing[:5])
            + (" ..." if len(missing) > 5 else "")
        )
    if len(selected) != len(stream_items):
        raise RuntimeError(
            "PatchCore stream filtering did not produce exactly one dataset item per stream item."
        )
    test_dataset.data_to_iterate = selected


class PatchCoreWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        if not os.path.isdir(LOCAL_PATH):
            raise _setup_error(BASELINE_NAME, LOCAL_PATH)
        memory_policy, _ = validate_execution_contract(
            config,
            baseline_name=BASELINE_NAME,
            supported_memory_policies={"default/SCS", "FIFO"},
        )

        category = str(config.get("category") or _cfg(config, "category", "bottle"))
        seed = _cfg(config, "seed", 0, int)
        resize = _cfg(config, "resize", 256, int)
        imagesize = _cfg(config, "imagesize", 224, int)
        backbone_name = str(_cfg(config, "backbone", "wideresnet50"))
        layers = _csv_list(_cfg(config, "layers", None), ["layer2", "layer3"])
        sampler_name = str(_cfg(config, "sampler", "approx_greedy_coreset"))
        sampler_percentage = _cfg(config, "sampler_percentage", 0.1, float)
        if memory_policy == "FIFO":
            sampler_name = "fifo"
            sampler_percentage = _cfg(
                config,
                "fifo_memory_fraction",
                sampler_percentage,
                float,
            )
        pretrain_embed_dimension = _cfg(config, "pretrain_embed_dimension", 1024, int)
        target_embed_dimension = _cfg(config, "target_embed_dimension", 1024, int)
        anomaly_scorer_num_nn = _cfg(config, "anomaly_scorer_num_nn", 1, int)
        patchsize = _cfg(config, "patchsize", 3, int)
        model_cache_enabled = _cfg(config, "model_cache", True, bool)
        model_cache_root = Path(
            _cfg(config, "model_cache_root", "results/latest/patchcore_model_cache")
        )

        if not (Path(dataset_root) / category).is_dir():
            raise RuntimeError(f"MVTec category not found: {Path(dataset_root) / category}")

        stream_items = _load_stream_items(stream_path, required=True)
        cache_dir = model_cache_root / _cache_key(
            {
                "category": category,
                "seed": seed,
                "resize": resize,
                "imagesize": imagesize,
                "backbone": backbone_name,
                "layers": layers,
                "sampler": sampler_name,
                "sampler_percentage": sampler_percentage,
                "memory_policy": memory_policy,
                "pretrain_embed_dimension": pretrain_embed_dimension,
                "target_embed_dimension": target_embed_dimension,
                "anomaly_scorer_num_nn": anomaly_scorer_num_nn,
                "patchsize": patchsize,
                "dataset_root": str(Path(dataset_root).resolve()),
            }
        )
        score_cache_file = _score_cache_path(cache_dir)
        score_cache = _load_score_cache(score_cache_file) if model_cache_enabled else {}
        cached_rows = _rows_from_score_cache(score_cache, stream_items, dataset_root)
        if cached_rows is not None:
            output_path = Path(output_csv)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(cached_rows)
            return

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

        batch_size = _cfg(config, "batch_size", 2, int)
        num_workers = _cfg(config, "num_workers", 0, int)
        faiss_on_gpu = _cfg(config, "faiss_on_gpu", False, bool)
        faiss_num_workers = _cfg(config, "faiss_num_workers", 8, int)
        max_test_images_raw = _cfg(config, "max_test_images", None)
        max_test_images = (
            int(max_test_images_raw) if max_test_images_raw not in {None, ""} else None
        )

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
        _filter_test_dataset_to_stream(test_dataset, stream_items, dataset_root)

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

        loaded_from_cache = False
        if model_cache_enabled and _valid_patchcore_cache(cache_dir):
            try:
                model = patchcore.patchcore.PatchCore(device)
                model.load_from_path(str(cache_dir), device=device, nn_method=nn_method)
                loaded_from_cache = True
            except Exception as error:  # pragma: no cover - cache corruption recovery
                print(f"WARNING[patchcore_cache_ignored]: {error}", file=sys.stderr)
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

        if not loaded_from_cache:
            if device.type == "cuda":
                torch.cuda.empty_cache()
            model.fit(train_loader)
            if model_cache_enabled:
                cache_dir.mkdir(parents=True, exist_ok=True)
                model.save_to_path(str(cache_dir))

        rows = self._predict_rows(
            model=model,
            test_loader=test_loader,
            category=category,
            device=device,
            max_test_images=max_test_images,
            torch=torch,
        )
        rows = _apply_stream_order(rows, stream_path, dataset_root, require_stream=True)
        for idx, row in enumerate(rows):
            row["stream_index"] = idx
        if model_cache_enabled:
            score_cache = _merge_rows_into_score_cache(score_cache, rows, dataset_root)
            _write_score_cache(score_cache_file, score_cache)

        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _make_sampler(sampler_module: Any, name: str, percentage: float, device: Any) -> Any:
        if name == "identity":
            return sampler_module.IdentitySampler()
        if name == "fifo":
            return _FIFOSampler(percentage)
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
