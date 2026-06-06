#!/usr/bin/env python3
"""Gate-2 bank-trace runner for the VisA replication of the RareCLIP/SCS order
mechanism (LOCKED RULE 6). Mirrors experiments/run_banktrace_gate2.py (MVTec) but
on VisA {candle, macaroni1, macaroni2} with the VisA checkpoint and dataset root,
into a SEPARATE output directory so MVTec artifacts are never touched.

90 jobs = 3 cat x seeds 0-9 x {iid, bursty, bursty-repeat}. The candle/seed0
bursty base + repeat are seeded from Step 3, so 88 are executed here. Uses
ABSOLUTE output paths (the Step-3 relative-path issue is avoided). Diagnostic
only: read-only bank trace AFTER the latency timer; scoring path, flags, and the
MVTec driver/summarizer are unchanged. Resumable (skips existing *_banktrace.csv).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.baselines.rareclip import RareCLIPWrapper  # noqa: E402

STREAM_ROOT = ROOT / "results/latest/paper_candidate/visa/rareclip/default_scs/none"
OUT = ROOT / "results/latest/paper_candidate/diagnostic_rareclip_scs_banktrace_visa_gate2"
LOG = OUT / "gate2_run.log"
DATASET_ROOT = "data/visa/1cls"
CHECKPOINT = "external/RareCLIP/weights/visa_pretrained.pth"

CATS = ["candle", "macaroni1", "macaroni2"]
SEEDS = range(10)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as handle:
        handle.write(line + "\n")


def jobs() -> list[tuple[str, int, str, bool]]:
    js: list[tuple[str, int, str, bool]] = []
    for cat in CATS:
        for seed in SEEDS:
            for order in ("iid", "bursty"):
                js.append((cat, seed, order, False))
            js.append((cat, seed, "bursty", True))  # same-order repeat (noise floor)
    return js


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_cfg = {
        "memory_policy": "default/SCS",
        "calibration": "none",
        "diagnostic_bank_trace": True,
        "checkpoint_path": CHECKPOINT,
    }
    all_jobs = jobs()
    log(f"VisA Gate-2 start: {len(all_jobs)} jobs ({len(CATS)} cat x {len(list(SEEDS))} seed x [iid, bursty, bursty_rep])")
    t_all = time.time()
    done = ran = 0
    for cat, seed, order, rep in all_jobs:
        stem = f"{cat}_{order}_seed{seed}" + ("_rep" if rep else "")
        out_csv = OUT / f"{stem}.csv"            # absolute -> bank trace lands here
        banktrace = OUT / f"{stem}_banktrace.csv"
        done += 1
        if banktrace.exists():
            log(f"SKIP exists  {stem}  ({done}/{len(all_jobs)})")
            continue
        stream = (
            STREAM_ROOT / cat / "production_runs"
            / f"{cat}_{order}_eps_0_seed_{seed}" / "stream.json"
        )
        if not stream.exists():
            log(f"ERROR missing stream  {stream}")
            continue
        cfg = dict(base_cfg, category=cat)
        t0 = time.time()
        RareCLIPWrapper().run(
            stream_path=str(stream),
            dataset_root=DATASET_ROOT,
            output_csv=str(out_csv),
            config=cfg,
        )
        ran += 1
        log(f"DONE {stem} in {time.time() - t0:.0f}s  ({done}/{len(all_jobs)})")
    log(
        f"VisA Gate-2 complete: ran {ran}, accounted {done}/{len(all_jobs)} "
        f"in {(time.time() - t_all) / 3600:.2f}h"
    )


if __name__ == "__main__":
    main()
