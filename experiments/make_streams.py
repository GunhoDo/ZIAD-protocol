#!/usr/bin/env python3
"""Write minimal stream placeholders for the P0 matrix.

The files document stream settings only; they do not contain fake image/order
records. Real streams should replace the empty `items` arrays.
"""
from __future__ import annotations

import json
from pathlib import Path

STREAM_TYPES = ["iid", "bursty"]
EPSILONS = [0, 0.01, 0.05]
PREVALENCE = 0.05


def main() -> None:
    out = Path("results/latest/streams")
    out.mkdir(parents=True, exist_ok=True)
    for stream_type in STREAM_TYPES:
        for eps in EPSILONS:
            path = out / f"stream_{stream_type}_eps_{str(eps).replace('.', 'p')}.json"
            payload = {
                "status": "placeholder",
                "stream_type": stream_type,
                "prevalence": PREVALENCE,
                "contamination_epsilon": eps,
                "seed": "TODO",
                "items": [],
                "note": "TODO: replace with real ordered image records before measuring results.",
            }
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            print(path)


if __name__ == "__main__":
    main()
