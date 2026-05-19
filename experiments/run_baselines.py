#!/usr/bin/env python3
"""Create placeholder baseline score CSV for the reduced P0 pipeline.

No model inference is performed here. The output is explicitly marked as a
placeholder so it cannot be mistaken for measured findings.
"""
from __future__ import annotations

from pathlib import Path

HEADER = "stream_index,image_path,label,category,anomaly_score,latency_ms,peak_vram_mb,status\n"
PLACEHOLDER = "TODO,TODO,TODO,TODO,TODO,TODO,TODO,placeholder_not_measured\n"


def main() -> None:
    path = Path("results/latest/scores.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + PLACEHOLDER)
    print(path)


if __name__ == "__main__":
    main()
