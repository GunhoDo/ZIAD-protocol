#!/usr/bin/env python3
"""Gate-2 bank-trace runner for the VisA multi-category CONCATENATION stress-test
(LOCKED RULE 7). 3 cyclic permutations x seeds 0-4 of concatenated VisA streams
(candle/macaroni1/macaroni2, ~315 each), each run base + same-order repeat = 30 cells.
perm0/seed0 base+repeat are seeded from Gate 1, so 28 are executed here.

Mirrors run_banktrace_visa_gate2.py: absolute output paths, VisA checkpoint, separate
output dir, read-only bank trace after the latency timer. Scoring path, flags, MVTec/VisA
drivers and outputs are untouched. Resumable (skips existing *_banktrace.csv).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.baselines.rareclip import RareCLIPWrapper  # noqa: E402

STREAM_ROOT = ROOT / "results/latest/paper_candidate/concat_visa_streams"
OUT = ROOT / "results/latest/paper_candidate/diagnostic_rareclip_scs_concat_visa_gate2"
LOG = OUT / "gate2_run.log"
DATASET_ROOT = "data/visa/1cls"
CHECKPOINT = "external/RareCLIP/weights/visa_pretrained.pth"

PERMS = range(3)
SEEDS = range(5)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as handle:
        handle.write(line + "\n")


def jobs() -> list[tuple[int, int, bool]]:
    js: list[tuple[int, int, bool]] = []
    for p in PERMS:
        for s in SEEDS:
            js.append((p, s, False))  # base
            js.append((p, s, True))   # same-order repeat (noise floor)
    return js


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_cfg = {
        "category": "candle",  # placeholder for the dir-check; items carry their own category
        "memory_policy": "default/SCS",
        "calibration": "none",
        "diagnostic_bank_trace": True,
        "checkpoint_path": CHECKPOINT,
    }
    all_jobs = jobs()
    log(f"Concat Gate-2 start: {len(all_jobs)} jobs ({len(list(PERMS))} perm x {len(list(SEEDS))} seed x [base, repeat])")
    t_all = time.time()
    done = ran = 0
    for p, s, rep in all_jobs:
        stem = f"perm{p}_seed{s}" + ("_rep" if rep else "")
        out_csv = OUT / f"{stem}.csv"
        banktrace = OUT / f"{stem}_banktrace.csv"
        done += 1
        if banktrace.exists():
            log(f"SKIP exists  {stem}  ({done}/{len(all_jobs)})")
            continue
        stream = STREAM_ROOT / f"perm{p}_seed{s}" / "stream.json"
        if not stream.exists():
            log(f"ERROR missing stream  {stream}")
            continue
        t0 = time.time()
        RareCLIPWrapper().run(
            stream_path=str(stream),
            dataset_root=DATASET_ROOT,
            output_csv=str(out_csv),
            config=dict(base_cfg),
        )
        ran += 1
        log(f"DONE {stem} in {time.time() - t0:.0f}s  ({done}/{len(all_jobs)})")
    log(
        f"Concat Gate-2 complete: ran {ran}, accounted {done}/{len(all_jobs)} "
        f"in {(time.time() - t_all) / 3600:.2f}h"
    )


if __name__ == "__main__":
    main()
