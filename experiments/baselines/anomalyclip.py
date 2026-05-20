"""AnomalyCLIP baseline wrapper.

The upstream AnomalyCLIP scripts evaluate full datasets through their own
loader.  This wrapper keeps the project stream JSON as the source of truth and
runs the upstream single-image scoring path in stream order.  Image-level
scores use the same `text_probs[:, 0, 1]` anomaly probability that upstream
`test.py` records for image-level metrics.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from PIL import Image

from .base import BaselineWrapper, _setup_error

BASELINE_NAME = "AnomalyCLIP"
LOCAL_PATH = "external/AnomalyCLIP"
DEFAULT_CHECKPOINT = "external/AnomalyCLIP/checkpoints/9_12_4_multiscale/epoch_15.pth"
DEFAULT_CLIP_CACHE = "external/AnomalyCLIP/.cache/clip"
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
    env_key = "ANOMALYCLIP_" + key.upper()
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


def _ensure_anomalyclip_importable() -> None:
    root = Path(LOCAL_PATH).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _dependency_error(error: ImportError) -> RuntimeError:
    return RuntimeError(
        "AnomalyCLIP dependency import failed. Install the local AnomalyCLIP "
        "runtime dependencies before running the wrapper, e.g.\n"
        "  python3 -m pip install -r external/AnomalyCLIP/requirements.txt\n"
        "Original import error: "
        f"{error}"
    )


@contextmanager
def _temporary_cwd(path: str | Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve()


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


def _image_score(text_probs: Any, anomaly_map: Any, score_source: str) -> float:
    if score_source == "text_prob":
        array = np.asarray(text_probs.detach().cpu(), dtype=np.float32).reshape(-1)
        if array.size != 1:
            raise RuntimeError(f"AnomalyCLIP produced unexpected text score shape: {array.shape}")
        return float(array[0])
    if score_source == "map_max":
        array = np.asarray(anomaly_map.detach().cpu(), dtype=np.float32)
        if array.size == 0:
            raise RuntimeError("AnomalyCLIP produced an empty anomaly map.")
        return float(array.max())
    raise RuntimeError(f"Unsupported AnomalyCLIP score_source: {score_source}")


class AnomalyCLIPWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        if not os.path.isdir(LOCAL_PATH):
            raise _setup_error(BASELINE_NAME, LOCAL_PATH)

        _ensure_anomalyclip_importable()
        try:
            import torch
            from scipy.ndimage import gaussian_filter

            import AnomalyCLIP_lib
            from prompt_ensemble import AnomalyCLIP_PromptLearner
            from utils import get_transform
        except ImportError as error:  # pragma: no cover - environment-dependent
            raise _dependency_error(error) from error

        dataset_root_path = _resolve_repo_path(dataset_root)
        category = str(config.get("category") or _cfg(config, "category", "bottle"))
        if not (dataset_root_path / category).is_dir():
            raise RuntimeError(f"MVTec category not found: {dataset_root_path / category}")

        checkpoint_path = _resolve_repo_path(str(_cfg(config, "checkpoint_path", DEFAULT_CHECKPOINT)))
        if not checkpoint_path.is_file():
            raise RuntimeError(f"AnomalyCLIP checkpoint is required but missing: {checkpoint_path}")

        stream_items = _load_stream_items(stream_path)
        image_size = _cfg(config, "image_size", 518, int)
        depth = _cfg(config, "depth", 9, int)
        n_ctx = _cfg(config, "n_ctx", 12, int)
        t_n_ctx = _cfg(config, "t_n_ctx", 4, int)
        features_list = _csv_ints(_cfg(config, "features_list", None), (6, 12, 18, 24))
        feature_map_layer = _csv_ints(_cfg(config, "feature_map_layer", None), (0, 1, 2, 3))
        sigma = _cfg(config, "sigma", 4, int)
        dpam_layer = _cfg(config, "dpam_layer", 20, int)
        score_source = str(_cfg(config, "score_source", "text_prob"))
        clip_model_name = str(_cfg(config, "clip_model_name", "ViT-L/14@336px"))
        clip_cache = _resolve_repo_path(str(_cfg(config, "clip_download_root", DEFAULT_CLIP_CACHE)))
        force_cpu = _cfg(config, "use_cpu", not torch.cuda.is_available(), bool)
        device = torch.device("cpu" if force_cpu or not torch.cuda.is_available() else "cuda:0")

        clip_cache.mkdir(parents=True, exist_ok=True)
        parameters = {
            "Prompt_length": n_ctx,
            "learnabel_text_embedding_depth": depth,
            "learnabel_text_embedding_length": t_n_ctx,
        }
        args = SimpleNamespace(image_size=image_size)

        with _temporary_cwd(Path(LOCAL_PATH).resolve()):
            model, _ = AnomalyCLIP_lib.load(
                clip_model_name,
                device=str(device),
                design_details=parameters,
                download_root=str(clip_cache),
            )
            model.eval()
            preprocess, _ = get_transform(args)
            prompt_learner = AnomalyCLIP_PromptLearner(model.to("cpu"), parameters)
            checkpoint = torch.load(str(checkpoint_path), map_location="cpu")
            prompt_learner.load_state_dict(checkpoint["prompt_learner"])
            prompt_learner.to(device)
            model.to(device)
            model.visual.DAPM_replace(DPAM_layer=dpam_layer)

            prompts, tokenized_prompts, compound_prompts_text = prompt_learner(cls_id=None)
            text_features = model.encode_text_learn(
                prompts,
                tokenized_prompts,
                compound_prompts_text,
            ).float()
            text_features = torch.stack(torch.chunk(text_features, dim=0, chunks=2), dim=1)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            rows = self._predict_rows(
                model=model,
                preprocess=preprocess,
                text_features=text_features,
                stream_items=stream_items,
                dataset_root=dataset_root_path,
                category=category,
                image_size=image_size,
                features_list=features_list,
                feature_map_start=int(feature_map_layer[0]),
                sigma=sigma,
                dpam_layer=dpam_layer,
                score_source=score_source,
                device=device,
                torch=torch,
                anomalyclip_lib=AnomalyCLIP_lib,
                gaussian_filter=gaussian_filter,
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
        preprocess: Any,
        text_features: Any,
        stream_items: list[dict[str, Any]],
        dataset_root: str | Path,
        category: str,
        image_size: int,
        features_list: tuple[int, ...],
        feature_map_start: int,
        sigma: int,
        dpam_layer: int,
        score_source: str,
        device: Any,
        torch: Any,
        anomalyclip_lib: Any,
        gaussian_filter: Any,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in stream_items:
            image_path = _resolve_stream_image_path(str(item["image_path"]), dataset_root)
            image = Image.open(image_path).convert("RGB")
            tensor = preprocess(image).reshape(1, 3, image_size, image_size).to(device)

            if device.type == "cuda":
                torch.cuda.synchronize(device)
                torch.cuda.reset_peak_memory_stats(device)
            start = time.perf_counter()
            with torch.no_grad():
                image_features, patch_features = model.encode_image(
                    tensor,
                    list(features_list),
                    DPAM_layer=dpam_layer,
                )
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_probs = image_features @ text_features.permute(0, 2, 1)
                text_probs = (text_probs / 0.07).softmax(-1)
                text_probs = text_probs[:, 0, 1]

                anomaly_map_list = []
                for idx, patch_feature in enumerate(patch_features):
                    if idx < feature_map_start:
                        continue
                    patch_feature = patch_feature / patch_feature.norm(dim=-1, keepdim=True)
                    similarity, _ = anomalyclip_lib.compute_similarity(
                        patch_feature,
                        text_features[0],
                    )
                    similarity_map = anomalyclip_lib.get_similarity_map(
                        similarity[:, 1:, :],
                        image_size,
                    )
                    anomaly_map_list.append((similarity_map[..., 1] + 1 - similarity_map[..., 0]) / 2.0)
                if not anomaly_map_list:
                    raise RuntimeError("AnomalyCLIP produced no anomaly maps for configured layers.")
                anomaly_map = torch.stack(anomaly_map_list).sum(dim=0)
                anomaly_map = torch.stack(
                    [
                        torch.from_numpy(gaussian_filter(frame, sigma=sigma))
                        for frame in anomaly_map.detach().cpu()
                    ],
                    dim=0,
                )
                score = _image_score(text_probs, anomaly_map, score_source)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
                peak_vram_mb = torch.cuda.max_memory_allocated(device) / (1024 * 1024)
            else:
                peak_vram_mb = 0.0
            latency_ms = (time.perf_counter() - start) * 1000

            rows.append(
                {
                    "stream_index": item["stream_index"],
                    "image_path": str(item["image_path"]),
                    "label": int(item["label"]),
                    "category": str(item.get("category", category)),
                    "anomaly_score": f"{score:.10f}",
                    "latency_ms": f"{latency_ms:.4f}",
                    "peak_vram_mb": f"{peak_vram_mb:.2f}",
                    "status": "measured",
                }
            )
        return rows


def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    AnomalyCLIPWrapper().run(stream_path, dataset_root, output_csv, config)
