#!/usr/bin/env python3
"""Generate deterministic MVTec stream JSON for ZIAD smoke/P0 runs.

This module intentionally implements the first PatchCore-focused stream protocol
slice only.  It constructs evaluation streams from MVTec ``test/*`` samples,
records requested-vs-applied stream statistics, and never duplicates samples to
force a requested prevalence/contamination target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

GENERATOR_VERSION = "mvtec-stream-generator-v1"
SELECTION_POLICY_VERSION = "closest-ratio-no-duplicates-v1"
FRACTION_TOLERANCE = Decimal("1e-12")
IMAGE_SUFFIXES = {".bmp", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
PLACEHOLDER_STREAM_TYPES = ["iid", "bursty"]
PLACEHOLDER_EPSILONS = [0, 0.01, 0.05]
PLACEHOLDER_PREVALENCE = 0.05


@dataclass(frozen=True)
class StreamSample:
    path: Path
    rel_path: str
    label: int
    category: str
    source_split: str
    anomaly_type: str


def _warning(code: str, message: str, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    payload.update(details)
    return payload


def _decimal(value: Any, name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be numeric, got {value!r}") from error


def _decimal_float(value: Decimal) -> float:
    return float(value)


def _validate_fraction(value: Any, name: str) -> Decimal:
    parsed = _decimal(value, name)
    if parsed < 0 or parsed > 1:
        raise ValueError(f"{name} must be in [0, 1], got {value!r}")
    return parsed


def _validate_int(value: Any, name: str, *, positive: bool = False) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        parsed = int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer, got {value!r}") from error
    if positive and parsed <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
    return parsed


def _stable_round(value: Decimal) -> int:
    # Python's round(Decimal) uses banker's rounding, matching round(t * L) in
    # the approved PRD while avoiding binary float drift.
    return int(round(value))


def _ratio_distance(anomaly_count: int, length: int, target: Decimal) -> Decimal:
    return abs((Decimal(anomaly_count) / Decimal(length)) - target)


def _config_hash(config: dict[str, Any]) -> str:
    """Hash only portable stream-construction settings.

    Absolute dataset roots are intentionally excluded so the same logical stream
    config hashes identically across machines with different checkout paths.
    """
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def enumerate_mvtec_samples(dataset_root: str | Path, category: str) -> list[StreamSample]:
    root = Path(dataset_root)
    category_root = root / category
    test_root = category_root / "test"
    if not test_root.is_dir():
        raise FileNotFoundError(f"MVTec test split not found: {test_root}")

    samples: list[StreamSample] = []
    for anomaly_dir in sorted(p for p in test_root.iterdir() if p.is_dir()):
        anomaly_type = anomaly_dir.name
        label = 0 if anomaly_type == "good" else 1
        for image in sorted(p for p in anomaly_dir.rglob("*") if p.is_file()):
            if image.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            samples.append(
                StreamSample(
                    path=image,
                    rel_path=image.relative_to(root).as_posix(),
                    label=label,
                    category=category,
                    source_split="test",
                    anomaly_type=anomaly_type,
                )
            )
    if not samples:
        raise RuntimeError(f"No MVTec test images found under {test_root}")
    return samples


def choose_counts(
    normal_count: int,
    anomaly_count: int,
    target_anomaly_fraction: Decimal,
    requested_length: int | None,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Return selected normal/anomaly counts using the approved lexicographic rule."""
    warnings: list[dict[str, Any]] = []
    total = normal_count + anomaly_count
    if total == 0:
        raise RuntimeError("Cannot build a stream from an empty sample pool")

    if requested_length is not None:
        length = requested_length
        if length > total:
            warnings.append(
                _warning(
                    "requested_length_clamped_no_duplicates",
                    "Requested stream length exceeds available no-duplicate sample pool; clamped.",
                    requested_length=requested_length,
                    applied_length=total,
                    available_total=total,
                )
            )
            length = total
        low = max(0, length - normal_count)
        high = min(anomaly_count, length)
        feasible = range(low, high + 1)
        selected_anomalies = min(
            feasible,
            key=lambda a: (
                _ratio_distance(a, length, target_anomaly_fraction),
                abs(a - _stable_round(target_anomaly_fraction * Decimal(length))),
                a,
            ),
        )
        return length - selected_anomalies, selected_anomalies, warnings

    best: tuple[Decimal, int, int, int, int] | None = None
    best_counts: tuple[int, int] | None = None
    for length in range(1, total + 1):
        low = max(0, length - normal_count)
        high = min(anomaly_count, length)
        for anomalies in range(low, high + 1):
            key = (
                _ratio_distance(anomalies, length, target_anomaly_fraction),
                -length,
                abs(anomalies - _stable_round(target_anomaly_fraction * Decimal(length))),
                anomalies,
                length,
            )
            if best is None or key < best:
                best = key
                best_counts = (length - anomalies, anomalies)
    assert best_counts is not None
    return best_counts[0], best_counts[1], warnings


def _chunked(items: list[StreamSample], size: int) -> list[list[StreamSample]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _burst_lengths(items: list[StreamSample]) -> list[int]:
    lengths: list[int] = []
    current = 0
    for item in items:
        if item.label == 1:
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def order_items(
    normals: list[StreamSample],
    anomalies: list[StreamSample],
    stream_type: str,
    seed: int,
    burst_length: int,
) -> tuple[list[StreamSample], dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    rng_normals = random.Random(f"{seed}:normals")
    rng_anomalies = random.Random(f"{seed}:anomalies")
    selected_normals = list(normals)
    selected_anomalies = list(anomalies)
    rng_normals.shuffle(selected_normals)
    rng_anomalies.shuffle(selected_anomalies)

    if stream_type == "iid":
        ordered = selected_normals + selected_anomalies
        random.Random(f"{seed}:iid").shuffle(ordered)
    elif stream_type == "bursty":
        chunks = _chunked(selected_anomalies, burst_length) if selected_anomalies else []
        gap_count = len(selected_normals) + 1
        gaps: list[list[StreamSample]] = [[] for _ in range(gap_count)]
        gap_order = list(range(gap_count))
        random.Random(f"{seed}:gaps").shuffle(gap_order)
        last_assigned_gap: int | None = None
        for chunk_index, chunk in enumerate(chunks):
            if chunk_index < len(gap_order):
                gap = gap_order[chunk_index]
                last_assigned_gap = gap
            else:
                gap = last_assigned_gap if last_assigned_gap is not None else 0
                warnings.append(
                    _warning(
                        "burst_blocks_merged_insufficient_normals",
                        "Not enough normal gaps to keep all anomaly chunks separated; chunks merged.",
                        chunk_index=chunk_index,
                        gap_index=gap,
                    )
                )
            gaps[gap].extend(chunk)

        ordered = []
        ordered.extend(gaps[0])
        for index, normal in enumerate(selected_normals):
            ordered.append(normal)
            ordered.extend(gaps[index + 1])
    else:
        raise ValueError(f"Unsupported stream_type: {stream_type!r}")

    burst_stats = _burst_lengths(ordered)
    return ordered, {
        "applied_burst_count": len(burst_stats),
        "applied_burst_lengths": burst_stats,
        "applied_max_burst_length": max(burst_stats) if burst_stats else 0,
    }, warnings


def _warn_if_adjusted(
    warnings: list[dict[str, Any]],
    requested: Decimal,
    applied: Decimal,
    code: str,
    label: str,
) -> None:
    if abs(requested - applied) > FRACTION_TOLERANCE:
        warnings.append(
            _warning(
                code,
                f"Requested {label} could not be matched exactly without duplicates.",
                requested=_decimal_float(requested),
                applied=_decimal_float(applied),
            )
        )


def build_stream(
    *,
    dataset_root: str | Path,
    category: str,
    dataset: str = "MVTec AD",
    stream_type: str,
    prevalence: Any,
    contamination_epsilon: Any,
    seed: Any,
    length: Any = None,
    burst_length: Any = 1,
) -> dict[str, Any]:
    stream_type = str(stream_type)
    if stream_type not in {"iid", "bursty"}:
        raise ValueError(f"stream_type must be 'iid' or 'bursty', got {stream_type!r}")
    prevalence_dec = _validate_fraction(prevalence, "prevalence")
    epsilon_dec = _decimal(contamination_epsilon, "contamination_epsilon")
    target = prevalence_dec + epsilon_dec
    if target < 0 or target > 1:
        raise ValueError(
            "prevalence + contamination_epsilon must be in [0, 1], "
            f"got {target}"
        )
    seed_int = _validate_int(seed, "stream.seed")
    length_int = None if length in {None, ""} else _validate_int(length, "stream.length", positive=True)
    burst_length_int = _validate_int(burst_length, "stream.burst_length", positive=True)

    samples = enumerate_mvtec_samples(dataset_root, category)
    normals_all = [sample for sample in samples if sample.label == 0]
    anomalies_all = [sample for sample in samples if sample.label == 1]
    selected_normal_count, selected_anomaly_count, warnings = choose_counts(
        len(normals_all), len(anomalies_all), target, length_int
    )
    if target > 0 and selected_anomaly_count == 0 and anomalies_all:
        warnings.append(
            _warning(
                "positive_target_no_anomalies_selected",
                "A positive anomaly target could not select anomalies under the feasible objective.",
                requested_target_anomaly_fraction=_decimal_float(target),
            )
        )
    if not normals_all:
        warnings.append(_warning("normal_pool_empty", "No normal test samples are available."))
    if not anomalies_all:
        warnings.append(_warning("anomaly_pool_empty", "No anomaly test samples are available."))

    rng_normals = random.Random(f"{seed_int}:select:normals")
    rng_anomalies = random.Random(f"{seed_int}:select:anomalies")
    normals_pool = list(normals_all)
    anomalies_pool = list(anomalies_all)
    rng_normals.shuffle(normals_pool)
    rng_anomalies.shuffle(anomalies_pool)
    selected_normals = normals_pool[:selected_normal_count]
    selected_anomalies = anomalies_pool[:selected_anomaly_count]

    ordered, burst_stats, order_warnings = order_items(
        selected_normals, selected_anomalies, stream_type, seed_int, burst_length_int
    )
    warnings.extend(order_warnings)

    applied_length = len(ordered)
    applied_anomaly_fraction = (
        Decimal(selected_anomaly_count) / Decimal(applied_length) if applied_length else Decimal(0)
    )
    applied_epsilon = applied_anomaly_fraction - prevalence_dec
    _warn_if_adjusted(
        warnings,
        target,
        applied_anomaly_fraction,
        "target_fraction_adjusted",
        "target anomaly fraction",
    )

    portable_config = {
        "dataset": dataset,
        "category": category,
        "stream_type": stream_type,
        "prevalence": str(prevalence_dec),
        "contamination_epsilon": str(epsilon_dec),
        "target_anomaly_fraction": str(target),
        "seed": seed_int,
        "length": length_int,
        "burst_length": burst_length_int,
    }

    items = []
    for index, sample in enumerate(ordered):
        items.append(
            {
                "stream_index": index,
                "image_path": sample.rel_path,
                "label": sample.label,
                "category": sample.category,
                "source_split": sample.source_split,
                "anomaly_type": sample.anomaly_type,
            }
        )

    metadata = {
        "stream_type": stream_type,
        "dataset": dataset,
        "dataset_root_name": Path(dataset_root).name,
        "category": category,
        "seed": seed_int,
        "generator_version": GENERATOR_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "config_hash": _config_hash(portable_config),
        "requested_prevalence": _decimal_float(prevalence_dec),
        "applied_prevalence": _decimal_float(applied_anomaly_fraction),
        "requested_contamination_epsilon": _decimal_float(epsilon_dec),
        "target_anomaly_fraction": _decimal_float(target),
        "applied_anomaly_fraction": _decimal_float(applied_anomaly_fraction),
        "applied_epsilon_equivalent": _decimal_float(applied_epsilon),
        "requested_stream_length": length_int,
        "applied_stream_length": applied_length,
        "available_normal_count": len(normals_all),
        "available_anomaly_count": len(anomalies_all),
        "selected_normal_count": selected_normal_count,
        "selected_anomaly_count": selected_anomaly_count,
        "requested_burst_length": burst_length_int if stream_type == "bursty" else None,
        "warnings": warnings,
        "scoring_mode": "stream_ordered_offline",
        "training_source": "train/good",
        "stream_source": "test/*",
        "latency_semantics": "offline_batch_amortized",
    }
    metadata.update(burst_stats)
    return {"metadata": metadata, "items": items}


def validate_stream_payload(payload: dict[str, Any]) -> None:
    required_item_fields = {
        "stream_index",
        "image_path",
        "label",
        "category",
        "source_split",
        "anomaly_type",
    }
    if "metadata" not in payload or not isinstance(payload["metadata"], dict):
        raise ValueError("Stream payload requires object metadata")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Stream payload requires non-empty items")
    seen_indices: set[int] = set()
    seen_paths: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each stream item must be an object")
        missing = sorted(required_item_fields - set(item))
        if missing:
            raise ValueError(f"Stream item missing required fields: {missing}")
        index = _validate_int(item["stream_index"], "stream_index")
        if index in seen_indices:
            raise ValueError(f"Duplicate stream_index: {index}")
        seen_indices.add(index)
        image_path = str(item["image_path"])
        if image_path in seen_paths:
            raise ValueError(f"Duplicate image_path: {image_path}")
        seen_paths.add(image_path)
        if int(item["label"]) not in {0, 1}:
            raise ValueError(f"Invalid item label: {item['label']!r}")
    if seen_indices != set(range(len(items))):
        raise ValueError("stream_index values must be contiguous from 0")


def write_stream(payload: dict[str, Any], output: str | Path) -> None:
    validate_stream_payload(payload)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_placeholder_streams(output_dir: str | Path = "results/latest/streams") -> None:
    """Refresh P0 placeholder stream contracts without fabricating item rows."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for stream_type in PLACEHOLDER_STREAM_TYPES:
        for eps in PLACEHOLDER_EPSILONS:
            path = out / f"stream_{stream_type}_eps_{str(eps).replace('.', 'p')}.json"
            payload = {
                "status": "placeholder",
                "metadata": {
                    "stream_type": stream_type,
                    "requested_prevalence": PLACEHOLDER_PREVALENCE,
                    "requested_contamination_epsilon": eps,
                    "generator_version": GENERATOR_VERSION,
                    "selection_policy_version": SELECTION_POLICY_VERSION,
                    "warnings": [
                        {
                            "code": "placeholder_not_measured",
                            "message": "Placeholder stream; replace with real ordered image records before measuring results.",
                        }
                    ],
                },
                "items": [],
            }
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            print(path)


def _load_config(path: str | Path) -> dict[str, Any]:
    """Load a smoke-style YAML config without making PyYAML a hard dependency."""
    config_path = Path(path)
    text = config_path.read_text()
    try:
        import yaml  # type: ignore
    except ImportError:
        cfg: dict[str, Any] = {}
        current_section: str | None = None
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not raw.startswith((" ", "\t")) and stripped.endswith(":"):
                current_section = stripped[:-1]
                cfg[current_section] = {}
                continue
            if ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            parsed: Any = value.strip().strip('"').strip("'")
            if parsed in {"", "null", "None"}:
                parsed = None
            elif parsed.lower() in {"true", "false"}:
                parsed = parsed.lower() == "true"
            target = cfg.get(current_section) if current_section and raw.startswith((" ", "\t")) else cfg
            if not isinstance(target, dict):
                target = cfg
            target[key.strip()] = parsed
        return cfg
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"Config must be a mapping: {config_path}")
    return loaded


def _build_stream_from_config(config: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    stream = config.get("stream") or {}
    outputs = config.get("outputs") or {}
    if not isinstance(stream, dict):
        raise ValueError("config.stream must be a mapping")
    if not isinstance(outputs, dict):
        raise ValueError("config.outputs must be a mapping")
    output = Path(stream.get("path") or outputs.get("stream") or "results/latest/stream_smoke.json")
    payload = build_stream(
        dataset_root=config.get("dataset_root", "data/mvtec_ad"),
        dataset=config.get("dataset", "MVTec AD"),
        category=config.get("category", "bottle"),
        stream_type=config.get("stream_type", "iid"),
        prevalence=config.get("prevalence", "0.05"),
        contamination_epsilon=config.get("contamination_epsilon", "0"),
        seed=stream.get("seed", "0"),
        length=stream.get("length"),
        burst_length=stream.get("burst_length", "1"),
    )
    return payload, output


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        help="Smoke-style YAML config to build a stream from.",
    )
    parser.add_argument("--dataset-root", default="data/mvtec_ad")
    parser.add_argument("--dataset", default="MVTec AD")
    parser.add_argument("--category", default="bottle")
    parser.add_argument("--stream-type", choices=["iid", "bursty"], default="iid")
    parser.add_argument("--prevalence", default="0.05")
    parser.add_argument("--contamination-epsilon", default="0")
    parser.add_argument("--seed", default="0")
    parser.add_argument("--length", default=None)
    parser.add_argument("--burst-length", default="1")
    parser.add_argument("--output", type=Path, default=Path("results/latest/stream_smoke.json"))
    parser.add_argument(
        "--placeholder-p0",
        action="store_true",
        help="Write placeholder P0 stream contracts under results/latest/streams.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/latest/streams"),
        help="Output directory for --placeholder-p0.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    if args.placeholder_p0:
        write_placeholder_streams(args.output_dir)
        return
    if args.config:
        payload, output = _build_stream_from_config(_load_config(args.config))
    else:
        payload = build_stream(
            dataset_root=args.dataset_root,
            dataset=args.dataset,
            category=args.category,
            stream_type=args.stream_type,
            prevalence=args.prevalence,
            contamination_epsilon=args.contamination_epsilon,
            seed=args.seed,
            length=args.length,
            burst_length=args.burst_length,
        )
        output = args.output
    write_stream(payload, output)
    for warning in payload["metadata"].get("warnings", []):
        print(f"WARNING[{warning['code']}]: {warning['message']}", file=sys.stderr)
    print(output)


if __name__ == "__main__":
    main()
