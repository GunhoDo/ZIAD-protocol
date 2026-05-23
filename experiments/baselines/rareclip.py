"""RareCLIP baseline wrapper.

RareCLIP is an online zero-shot method, so this wrapper keeps the project stream
JSON as the ordering source and calls the upstream `process_image_and_update`
method one image at a time.  The emitted image-level score is the upstream
`anomaly_score` returned by RareCLIP after combining text and rarity branches.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from PIL import Image

from .base import BaselineWrapper, _setup_error, validate_execution_contract

BASELINE_NAME = "RareCLIP"
LOCAL_PATH = "external/RareCLIP"
DEFAULT_CHECKPOINT = "external/RareCLIP/weights/mvtec_pretrained.pth"
DEFAULT_CLIP_CACHE = "external/cache"
KNOWN_CLIP_CACHE = "external/AnomalyCLIP/.cache/clip/ViT-L-14-336px.pt"
OPENAI_CLIP_FILENAME = "ViT-L-14-336px.pt"
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
    env_key = "RARECLIP_" + key.upper()
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


def _ensure_rareclip_importable() -> None:
    root = Path(LOCAL_PATH).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _dependency_error(error: ImportError) -> RuntimeError:
    return RuntimeError(
        "RareCLIP dependency import failed. Install the local RareCLIP runtime "
        "dependencies before running the wrapper, e.g.\n"
        "  python3 -m pip install -r external/RareCLIP/requirements.txt\n"
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


def _score_to_float(score: Any) -> float:
    if hasattr(score, "detach"):
        score = score.detach().cpu()
    array = np.asarray(score, dtype=np.float32).reshape(-1)
    if array.size != 1:
        raise RuntimeError(f"RareCLIP produced unexpected score shape: {array.shape}")
    return float(array[0])


def _contiguous(value: Any) -> Any:
    if hasattr(value, "contiguous"):
        return value.contiguous()
    return value


def _trim_tensor_fifo(tensor: Any, limit: int, *, preserve_prefix: int = 0) -> Any:
    if tensor is None or not hasattr(tensor, "shape") or len(tensor.shape) == 0:
        return tensor
    if limit < 1:
        raise RuntimeError("RareCLIP FIFO memory limit must be positive.")

    length = int(tensor.shape[0])
    prefix = max(0, min(int(preserve_prefix), length))
    mutable_length = length - prefix
    if mutable_length <= limit:
        return tensor

    prefix_part = tensor[:prefix] if prefix else None
    tail = tensor[-limit:]
    if prefix_part is None:
        return _contiguous(tail)
    if hasattr(prefix_part, "new_empty"):
        import torch

        return _contiguous(torch.cat((prefix_part, tail), dim=0))
    return np.concatenate((np.asarray(prefix_part), np.asarray(tail)), axis=0)


def _trim_similarity_fifo(similarity: Any, limit: int) -> Any:
    if similarity is None or not hasattr(similarity, "shape"):
        return similarity
    trimmed = similarity
    if len(trimmed.shape) >= 1 and int(trimmed.shape[0]) > limit:
        trimmed = trimmed[-limit:]
    if len(trimmed.shape) >= 2 and int(trimmed.shape[1]) > limit:
        trimmed = trimmed[:, -limit:]
    return _contiguous(trimmed)


def _install_fifo_sampler(model: Any) -> None:
    """Replace RareCLIP's patch sampler with oldest-first retention."""

    def fifo_sample(
        F_ref: Any = None,
        S_ref: Any = None,
        normal_fnum: int = 0,
        **_: Any,
    ) -> tuple[Any, Any, int]:
        limit = int(getattr(model, "sample_num", 0) or 0)
        if limit < 1 or F_ref is None or not hasattr(F_ref, "shape"):
            return F_ref, S_ref, normal_fnum

        length = int(F_ref.shape[0])
        drop = max(0, length - limit)
        if drop == 0:
            return F_ref, S_ref, normal_fnum

        F_ref = _contiguous(F_ref[-limit:])
        S_ref = _trim_similarity_fifo(S_ref, limit)
        normal_fnum = max(0, int(normal_fnum) - drop)
        return F_ref, S_ref, normal_fnum

    model.sample = fifo_sample


def _take_indices(value: Any, indices: list[int]) -> Any:
    if value is None or not hasattr(value, "shape") or len(value.shape) == 0:
        return value
    if hasattr(value, "detach"):
        return _contiguous(value[indices])
    return np.asarray(value)[indices]


def _take_similarity_indices(
    similarity: Any,
    indices: list[int],
    *,
    source_length: int | None = None,
) -> Any:
    if similarity is None or not hasattr(similarity, "shape"):
        return similarity
    selected = similarity
    if (
        len(selected.shape) >= 1
        and source_length is not None
        and int(selected.shape[0]) == int(source_length)
    ):
        selected = selected[indices]
    if len(selected.shape) >= 2:
        selected = selected[:, indices]
    return _contiguous(selected)


def _replace_with_last_and_trim(value: Any, replacement_index: int, limit: int) -> Any:
    if value is None or not hasattr(value, "shape") or len(value.shape) == 0:
        return value
    if int(value.shape[0]) <= limit:
        return value
    if hasattr(value, "clone"):
        updated = value.clone()
        updated[replacement_index] = updated[-1]
        return _contiguous(updated[:limit])
    updated = np.array(value, copy=True)
    updated[replacement_index] = updated[-1]
    return updated[:limit]


def _reservoir_reduce_tensor(
    value: Any,
    *,
    limit: int,
    seen: int,
    seed: int,
    preserve_prefix: int = 0,
) -> Any:
    if value is None or not hasattr(value, "shape") or len(value.shape) == 0:
        return value
    if limit < 1:
        raise RuntimeError("RareCLIP reservoir memory limit must be positive.")

    length = int(value.shape[0])
    prefix = max(0, min(int(preserve_prefix), length))
    mutable = value[prefix:] if prefix else value
    mutable_length = int(mutable.shape[0])
    if mutable_length <= limit:
        return value

    rng = np.random.default_rng(int(seed) + int(seen))
    if mutable_length == limit + 1:
        replacement_index = int(rng.integers(0, max(seen, limit + 1)))
        if replacement_index < limit:
            reduced = _replace_with_last_and_trim(mutable, replacement_index, limit)
        else:
            reduced = mutable[:limit]
    else:
        indices = sorted(int(index) for index in rng.choice(mutable_length, size=limit, replace=False))
        reduced = _take_indices(mutable, indices)

    if prefix == 0:
        return _contiguous(reduced)
    if hasattr(value, "clone"):
        import torch

        return _contiguous(torch.cat((value[:prefix], reduced), dim=0))
    return np.concatenate((np.asarray(value[:prefix]), np.asarray(reduced)), axis=0)


def _install_reservoir_sampler(model: Any, seed: int) -> None:
    """Replace RareCLIP's patch sampler with deterministic reservoir sampling."""
    rng = np.random.default_rng(seed)

    def reservoir_sample(
        F_ref: Any = None,
        S_ref: Any = None,
        normal_fnum: int = 0,
        **_: Any,
    ) -> tuple[Any, Any, int]:
        limit = int(getattr(model, "sample_num", 0) or 0)
        if limit < 1 or F_ref is None or not hasattr(F_ref, "shape"):
            return F_ref, S_ref, normal_fnum

        length = int(F_ref.shape[0])
        if length <= limit:
            return F_ref, S_ref, normal_fnum

        keep = sorted(int(index) for index in rng.choice(length, size=limit, replace=False))
        F_ref = _take_indices(F_ref, keep)
        S_ref = _take_similarity_indices(S_ref, keep, source_length=length)
        normal_fnum = sum(1 for index in keep if index < int(normal_fnum))
        return F_ref, S_ref, normal_fnum

    model.sample = reservoir_sample


def _trim_patch_grid_fifo(grid: Any, limit: int) -> None:
    if not isinstance(grid, list):
        return
    for region_index, region in enumerate(grid):
        if isinstance(region, dict):
            items = list(region.items())
        elif isinstance(region, list):
            items = list(enumerate(region))
        else:
            continue
        for layer, value in items:
            if value is None or not hasattr(value, "shape") or len(value.shape) == 0:
                continue
            if int(value.shape[0]) > limit:
                grid[region_index][layer] = _contiguous(value[-limit:])


def _trim_patch_similarity_grid_fifo(grid: Any, limit: int) -> None:
    if not isinstance(grid, list):
        return
    for region_index, region in enumerate(grid):
        if isinstance(region, dict):
            items = list(region.items())
        elif isinstance(region, list):
            items = list(enumerate(region))
        else:
            continue
        for layer, value in items:
            grid[region_index][layer] = _trim_similarity_fifo(value, limit)


def _apply_fifo_memory_policy(model: Any, memory_limit: int) -> None:
    """Keep RareCLIP online memories bounded by dropping oldest entries first."""
    limit = int(memory_limit)
    if limit < 1:
        raise RuntimeError("RareCLIP FIFO memory limit must be positive.")

    for attr in ("score_memory", "IF_memory"):
        value = getattr(model, attr, None)
        if value is not None:
            setattr(model, attr, _trim_tensor_fifo(value, limit))

    k_shot = int(getattr(model, "k_shot", 0) or 0)
    aaif_memory = getattr(model, "AAIF_memory", None)
    if isinstance(aaif_memory, dict):
        for layer, value in list(aaif_memory.items()):
            aaif_memory[layer] = _trim_tensor_fifo(
                value,
                limit,
                preserve_prefix=k_shot,
            )
    elif isinstance(aaif_memory, list):
        for layer, value in enumerate(list(aaif_memory)):
            aaif_memory[layer] = _trim_tensor_fifo(
                value,
                limit,
                preserve_prefix=k_shot,
            )

    _trim_patch_grid_fifo(getattr(model, "PFM", None), limit)
    _trim_patch_similarity_grid_fifo(getattr(model, "PSM", None), limit)


def _apply_reservoir_memory_policy(model: Any, memory_limit: int, seed: int) -> None:
    """Keep image-level RareCLIP memories bounded with reservoir replacement."""
    limit = int(memory_limit)
    if limit < 1:
        raise RuntimeError("RareCLIP reservoir memory limit must be positive.")

    seen = int(getattr(model, "_ziad_reservoir_seen", 0)) + 1
    model._ziad_reservoir_seen = seen

    for attr in ("score_memory", "IF_memory"):
        value = getattr(model, attr, None)
        if value is not None:
            setattr(
                model,
                attr,
                _reservoir_reduce_tensor(value, limit=limit, seen=seen, seed=seed),
            )

    k_shot = int(getattr(model, "k_shot", 0) or 0)
    aaif_memory = getattr(model, "AAIF_memory", None)
    if isinstance(aaif_memory, dict):
        for layer, value in list(aaif_memory.items()):
            aaif_memory[layer] = _reservoir_reduce_tensor(
                value,
                limit=limit,
                seen=seen,
                seed=seed + int(layer),
                preserve_prefix=k_shot,
            )
    elif isinstance(aaif_memory, list):
        for layer, value in enumerate(list(aaif_memory)):
            aaif_memory[layer] = _reservoir_reduce_tensor(
                value,
                limit=limit,
                seen=seen,
                seed=seed + int(layer),
                preserve_prefix=k_shot,
            )


def _prepare_openai_clip_cache(cache_dir: Path) -> None:
    """Reuse an already downloaded OpenAI CLIP weight when available.

    Upstream RareCLIP hard-codes `cache_dir='../cache'` relative to its repo.
    The AnomalyCLIP wrapper already downloads the exact same OpenAI
    ViT-L/14@336px file into a repo-local cache, so avoid a second network fetch
    by linking or copying it into RareCLIP's expected cache directory.
    """
    target = cache_dir / OPENAI_CLIP_FILENAME
    if target.exists():
        return
    source = _resolve_repo_path(KNOWN_CLIP_CACHE)
    if not source.is_file():
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source)
    except OSError:
        shutil.copyfile(source, target)


def _rareclip_args(config: dict[str, Any], checkpoint_path: Path) -> SimpleNamespace:
    use_cpu = _cfg(config, "use_cpu", True, bool)
    return SimpleNamespace(
        image_size=_cfg(config, "image_size", 518, int),
        gpu=-1 if use_cpu else _cfg(config, "gpu", 0, int),
        model=str(_cfg(config, "model", "ViT-L-14-336")),
        pretrained=str(_cfg(config, "pretrained", "openai")),
        load_path=str(checkpoint_path),
        features_list_text=list(_csv_ints(_cfg(config, "features_list_text", None), (12, 16, 20, 24))),
        features_list_rare=list(_csv_ints(_cfg(config, "features_list_rare", None), (6, 12, 18, 24))),
        keep_ftime=_cfg(config, "keep_ftime", 3.0, float),
        keep_fratio=_cfg(config, "keep_fratio", 0.333, float),
        keep_snum=_cfg(config, "keep_snum", 200, int),
        keep_inum=_cfg(config, "keep_inum", 1000, int),
        topk=_cfg(config, "topk", 3, int),
        LS_ratio=_cfg(config, "ls_ratio", _cfg(config, "LS_ratio", 0.01, float), float),
        Rs=_cfg(config, "rs", _cfg(config, "Rs", 1, int), int),
        Rs_freq=_cfg(config, "rs_freq", _cfg(config, "Rs_freq", 20, int), int),
        max_Rs_num=_cfg(config, "max_rs_num", _cfg(config, "max_Rs_num", 8, int), int),
        Rs_temp=_cfg(config, "rs_temp", _cfg(config, "Rs_temp", 200.0, float), float),
        text_temp=_cfg(config, "text_temp", 20.0, float),
        sigma=_cfg(config, "sigma", 4.0, float),
        rare_thd=_cfg(config, "rare_thd", 0.3, float),
        sampler=str(_cfg(config, "sampler", "SCS")),
        k_shot=_cfg(config, "k_shot", 0, int),
        other=str(_cfg(config, "other", "")),
    )


class RareCLIPWrapper(BaselineWrapper):
    def run(self, stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
        if not os.path.isdir(LOCAL_PATH):
            raise _setup_error(BASELINE_NAME, LOCAL_PATH)
        memory_policy, _ = validate_execution_contract(
            config,
            baseline_name=BASELINE_NAME,
            supported_memory_policies={"default/SCS", "FIFO", "Reservoir"},
        )

        _ensure_rareclip_importable()
        try:
            import torch
            from rareclip import RareCLIP
            from rareclip_d import RareCLIP_d
        except ImportError as error:  # pragma: no cover - environment-dependent
            raise _dependency_error(error) from error

        dataset_root_path = _resolve_repo_path(dataset_root)
        category = str(config.get("category") or _cfg(config, "category", "bottle"))
        if not (dataset_root_path / category).is_dir():
            raise RuntimeError(f"MVTec category not found: {dataset_root_path / category}")

        checkpoint_path = _resolve_repo_path(str(_cfg(config, "checkpoint_path", DEFAULT_CHECKPOINT)))
        if not checkpoint_path.is_file():
            raise RuntimeError(f"RareCLIP checkpoint is required but missing: {checkpoint_path}")

        stream_items = _load_stream_items(stream_path)
        update_memory = _cfg(config, "online", True, bool)
        direct = _cfg(config, "direct", False, bool)
        args = _rareclip_args(config, checkpoint_path)
        fifo_memory_size = _cfg(config, "fifo_memory_size", args.keep_inum, int)
        reservoir_memory_size = _cfg(config, "reservoir_memory_size", args.keep_inum, int)
        reservoir_seed = _cfg(config, "reservoir_seed", _cfg(config, "seed", 0, int), int)

        cache_dir = _resolve_repo_path(str(_cfg(config, "clip_cache_dir", DEFAULT_CLIP_CACHE)))
        _prepare_openai_clip_cache(cache_dir)

        with _temporary_cwd(Path(LOCAL_PATH).resolve()):
            model = RareCLIP_d(args) if direct else RareCLIP(args)
            if memory_policy == "FIFO":
                _install_fifo_sampler(model)
            elif memory_policy == "Reservoir":
                _install_reservoir_sampler(model, reservoir_seed)
            if hasattr(model.clip_model, "eval"):
                model.clip_model.eval()
            model.renew_memory()
            rows = self._predict_rows(
                model=model,
                stream_items=stream_items,
                dataset_root=dataset_root_path,
                category=category,
                update_memory=update_memory,
                device=model.device,
                torch=torch,
                memory_policy=memory_policy,
                memory_limit=(
                    reservoir_memory_size if memory_policy == "Reservoir" else fifo_memory_size
                ),
                memory_seed=reservoir_seed,
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
        update_memory: bool,
        device: Any,
        torch: Any,
        memory_policy: str = "default/SCS",
        memory_limit: int | None = None,
        memory_seed: int = 0,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        device_obj = torch.device(device)
        for item in stream_items:
            image_path = _resolve_stream_image_path(str(item["image_path"]), dataset_root)
            image = Image.open(image_path).convert("RGB")
            tensor = model.preprocess(image).unsqueeze(0).to(device_obj)

            if device_obj.type == "cuda":
                torch.cuda.synchronize(device_obj)
                torch.cuda.reset_peak_memory_stats(device_obj)
            start = time.perf_counter()
            with torch.no_grad():
                result = model.process_image_and_update(tensor, update=update_memory)
                if update_memory and memory_policy == "FIFO":
                    _apply_fifo_memory_policy(model, int(memory_limit or 1))
                elif update_memory and memory_policy == "Reservoir":
                    _apply_reservoir_memory_policy(
                        model,
                        int(memory_limit or 1),
                        int(memory_seed),
                    )
            if result is None:
                raise RuntimeError("RareCLIP returned no score; k_shot warmup is unsupported for score rows.")
            _, anomaly_score = result
            if device_obj.type == "cuda":
                torch.cuda.synchronize(device_obj)
                peak_vram_mb = torch.cuda.max_memory_allocated(device_obj) / (1024 * 1024)
            else:
                peak_vram_mb = 0.0
            latency_ms = (time.perf_counter() - start) * 1000

            rows.append(
                {
                    "stream_index": item["stream_index"],
                    "image_path": str(item["image_path"]),
                    "label": int(item["label"]),
                    "category": str(item.get("category", category)),
                    "anomaly_score": f"{_score_to_float(anomaly_score):.10f}",
                    "latency_ms": f"{latency_ms:.4f}",
                    "peak_vram_mb": f"{peak_vram_mb:.2f}",
                    "status": "measured",
                }
            )
        return rows


def run(stream_path: str, dataset_root: str, output_csv: str, config: dict) -> None:
    RareCLIPWrapper().run(stream_path, dataset_root, output_csv, config)
