#!/usr/bin/env python3
"""Generate the VisA multi-category concatenated streams for the distribution-shift
stress-test (LOCKED RULE 7). 3 cyclic permutations of {candle, macaroni1, macaroni2}
x seeds 0-4, each block ~105 (prevalence 0.05, eps=0, iid within block), so a
concatenated stream is ~315 > the 201 single-category cap. Same-order repeats reuse
the same stream.json (no separate file). Uses make_streams.build_concatenated_stream
(new function); build_stream and existing generators are untouched.

This is the Step-3 generator; running it writes stream.json files. Verification is
reported separately before any bank-trace run.
"""
from __future__ import annotations

import sys
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import make_streams as ms  # noqa: E402

DATASET = "VisA"
DATASET_ROOT = "data/visa/1cls"
BASE_CATS = ["candle", "macaroni1", "macaroni2"]
SEEDS = range(5)
PER_BLOCK_LENGTH = 105       # 100 normal + ~5 anomaly at prevalence 0.05
PREVALENCE = 0.05
OUT = ROOT / "results/latest/paper_candidate/concat_visa_streams"


def cyclic_permutations(cats: list[str]) -> list[list[str]]:
    """K cyclic rotations: each category appears once at each position."""
    return [list(islice(cats[i:] + cats[:i], len(cats))) for i in range(len(cats))]


def main() -> None:
    perms = cyclic_permutations(BASE_CATS)
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for p_idx, seq in enumerate(perms):
        for seed in SEEDS:
            payload = ms.build_concatenated_stream(
                dataset_root=DATASET_ROOT,
                categories=seq,
                dataset=DATASET,
                stream_type="iid",
                prevalence=PREVALENCE,
                contamination_epsilon=0.0,
                seed=seed,
                per_block_length=PER_BLOCK_LENGTH,
                burst_length=1,
            )
            out_path = OUT / f"perm{p_idx}_seed{seed}" / "stream.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            ms.write_stream(payload, out_path)
            written += 1
    print(f"permutations: {perms}")
    print(f"wrote {written} concatenated streams to {OUT.relative_to(ROOT)} "
          f"({len(perms)} perms x {len(list(SEEDS))} seeds)")


if __name__ == "__main__":
    main()
