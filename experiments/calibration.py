#!/usr/bin/env python3
"""Score calibration helpers for paper-ineligible smoke runs."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow `python3 experiments/calibration.py ...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError:  # pragma: no cover - optional CLI convenience
    yaml = None


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
SUPPORTED_CALIBRATIONS = {"none", "temperature_scaling"}
EPS = 1e-6


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if yaml is None:
        return {}
    loaded = yaml.safe_load(path.read_text()) or {}
    return loaded if isinstance(loaded, dict) else {}


def _temperature_from_config(config: dict[str, Any]) -> float:
    raw = config.get("temperature", config.get("calibration_temperature", 1.0))
    try:
        temperature = float(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"temperature must be numeric, got {raw!r}") from error
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError(f"temperature must be finite and > 0, got {temperature!r}")
    return temperature


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _format_score(value: float) -> str:
    return f"{value:.10f}"


def apply_temperature_scaling_to_scores_csv(
    scores_csv: Path,
    *,
    temperature: float,
    output_csv: Path | None = None,
) -> dict[str, Any]:
    """Apply deterministic temperature scaling to measured anomaly scores.

    Smoke runs do not have a held-out calibration split. This helper therefore
    treats measured anomaly scores as the only input signal: min-max maps them
    to probabilities, converts probabilities to logits, divides by temperature,
    and writes calibrated probabilities back into the common anomaly_score
    field. It is monotonic and auditable, but not a paper-ready fitted
    calibration procedure.
    """
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError(f"temperature must be finite and > 0, got {temperature!r}")

    output_csv = output_csv or scores_csv
    with scores_csv.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SCORE_FIELDS:
            raise ValueError(
                f"scores.csv header mismatch. Expected {SCORE_FIELDS}, got {reader.fieldnames}"
            )
        rows = list(reader)

    measured_indices: list[int] = []
    raw_scores: list[float] = []
    for index, row in enumerate(rows):
        if row.get("status") != "measured":
            continue
        measured_indices.append(index)
        try:
            raw_scores.append(float(row["anomaly_score"]))
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid anomaly_score at row {index}: {row.get('anomaly_score')!r}"
            ) from error

    warnings: list[str] = []
    if not raw_scores:
        raise ValueError("No measured rows available for temperature scaling")

    raw_min = min(raw_scores)
    raw_max = max(raw_scores)
    if raw_max == raw_min:
        calibrated = [0.5 for _ in raw_scores]
        warnings.append("constant_scores_temperature_scaled_to_0p5")
    else:
        scale = raw_max - raw_min
        calibrated = []
        for score in raw_scores:
            probability = (score - raw_min) / scale
            probability = min(max(probability, EPS), 1.0 - EPS)
            logit = math.log(probability / (1.0 - probability))
            calibrated.append(_sigmoid(logit / temperature))

    for row_index, score in zip(measured_indices, calibrated):
        rows[row_index]["anomaly_score"] = _format_score(score)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "method": "temperature_scaling",
        "temperature": temperature,
        "source": "score_minmax_logit_temperature",
        "input_scores_csv": str(scores_csv),
        "output_scores_csv": str(output_csv),
        "rows_calibrated": len(raw_scores),
        "raw_score_min": raw_min,
        "raw_score_max": raw_max,
        "warnings": warnings,
        "paper_allowed": False,
        "notes": (
            "Smoke-only postprocessing of measured scores; not calibration-set "
            "fitted paper evidence."
        ),
    }


def apply_calibration_from_config(
    scores_csv: Path,
    config: dict[str, Any],
    *,
    metadata_output: Path | None = None,
) -> dict[str, Any]:
    method = str(config.get("calibration", "none"))
    if method not in SUPPORTED_CALIBRATIONS:
        supported = ", ".join(sorted(SUPPORTED_CALIBRATIONS))
        raise ValueError(f"Unsupported calibration={method!r}. Supported: {supported}")
    if method == "none":
        metadata = {
            "method": "none",
            "rows_calibrated": 0,
            "scores_csv": str(scores_csv),
            "paper_allowed": False,
        }
    else:
        metadata = apply_temperature_scaling_to_scores_csv(
            scores_csv,
            temperature=_temperature_from_config(config),
        )

    if metadata_output is not None:
        metadata_output.parent.mkdir(parents=True, exist_ok=True)
        metadata_output.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-csv", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--metadata-output", required=True, type=Path)
    args = parser.parse_args()

    metadata = apply_calibration_from_config(
        args.scores_csv,
        _load_yaml_config(args.config),
        metadata_output=args.metadata_output,
    )
    print(
        "Calibration applied: "
        f"{metadata['method']} rows={metadata.get('rows_calibrated', 0)} "
        f"metadata={args.metadata_output}"
    )


if __name__ == "__main__":
    main()
