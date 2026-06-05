#!/usr/bin/env python3
"""Gate-2 bank-trace runner for the RareCLIP/SCS mechanism analysis.

Runs the full-pairing slice: MVTec AD {bottle, cable, capsule} x seeds 0-9, with
for each (cat, seed): an i.i.d. base run, a bursty base run, and a bursty REPEAT
run (same stream, second pass) that establishes the run-to-run noise floor
(LOCKED RULE 4/5 in docs/bank_trace_instrumentation_design.md). 90 jobs total;
the bottle/bursty/seed0 base is seeded from Gate 1, so 89 are executed here.

Diagnostic only: `diagnostic_bank_trace=True` writes read-only banktrace sidecars
AFTER the latency timer. The scoring path, flags, and generator scripts are
untouched. Resumable: any cell whose *_banktrace.csv already exists is skipped.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.baselines.rareclip import RareCLIPWrapper  # noqa: E402

STREAM_ROOT = (
    ROOT
    / "results/latest/paper_candidate/diagnostic_rareclip_scs_sl64"
    / "mvtec_ad/rareclip/default_scs/none"
)
OUT = ROOT / "results/latest/paper_candidate/diagnostic_rareclip_scs_banktrace_gate2"
LOG = OUT / "gate2_run.log"

CATS = ["bottle", "cable", "capsule"]
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
    }
    all_jobs = jobs()
    log(f"Gate-2 start: {len(all_jobs)} jobs ({len(CATS)} cat x {len(list(SEEDS))} seed x [iid, bursty, bursty_rep])")
    t_all = time.time()
    done = ran = 0
    for cat, seed, order, rep in all_jobs:
        stem = f"{cat}_{order}_seed{seed}" + ("_rep" if rep else "")
        out_csv = OUT / f"{stem}.csv"
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
            dataset_root="data/mvtec_ad",
            output_csv=str(out_csv),
            config=cfg,
        )
        ran += 1
        log(f"DONE {stem} in {time.time() - t0:.0f}s  ({done}/{len(all_jobs)})")
    log(
        f"Gate-2 complete: ran {ran}, accounted {done}/{len(all_jobs)} "
        f"in {(time.time() - t_all) / 3600:.2f}h"
    )


if __name__ == "__main__":
    main()
