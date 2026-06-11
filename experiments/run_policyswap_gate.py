#!/usr/bin/env python3
"""RareCLIP policy-swap probe (LOCKED RULE 9): swap ONLY the memory policy (FIFO,
Reservoir) on the existing MVTec bottle/cable/capsule L64 slice; reuse the SCS L64
streams; compare ΔB-I and bank-trace per policy against the existing SCS baseline.

Clean drop-in: memory_policy selects the sampler (_install_{fifo,reservoir}_sampler
replaces model.sample); the scoring path is untouched (scoring_path_modified=false; CODE
identity, not score identity). bank-trace ON. Reservoir uses reservoir_seed=stream seed so
base and same-order repeat are reproducible. Absolute output paths; resumable. MVTec/VisA/
concat/control artifacts and the SCS baseline are not touched.

180 cells = 2 policies x 3 cats x seeds 0-9 x {iid, bursty, bursty-repeat}.
--gate1 runs only FIFO+Reservoir bottle/seed0 bursty + bursty-repeat (4 cells) to reconfirm
per-policy d_rep determinism before the unattended run.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.baselines.rareclip import RareCLIPWrapper  # noqa: E402

STREAM_ROOT = ROOT / "results/latest/paper_candidate/diagnostic_rareclip_scs_sl64/mvtec_ad/rareclip/default_scs/none"
OUT = ROOT / "results/latest/paper_candidate/diagnostic_rareclip_scs_policyswap"
LOG = OUT / "policyswap_run.log"
CHECKPOINT = "external/RareCLIP/weights/mvtec_pretrained.pth"
POLICIES = ["FIFO", "Reservoir"]
CATS = ["bottle", "cable", "capsule"]
SEEDS = range(10)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as handle:
        handle.write(line + "\n")


def jobs(gate1: bool) -> list[tuple[str, str, int, str, bool]]:
    js: list[tuple[str, str, int, str, bool]] = []
    for policy in POLICIES:
        for cat in CATS:
            for seed in SEEDS:
                js.append((policy, cat, seed, "iid", False))
                js.append((policy, cat, seed, "bursty", False))
                js.append((policy, cat, seed, "bursty", True))  # same-order repeat (d_rep)
    if gate1:
        js = [j for j in js if j[1] == "bottle" and j[2] == 0 and j[3] == "bursty"]
    return js


def main(gate1: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_jobs = jobs(gate1)
    log(f"Policy-swap run ({'GATE1' if gate1 else 'FULL'}): {len(all_jobs)} cells")
    t_all = time.time()
    done = ran = 0
    for policy, cat, seed, order, rep in all_jobs:
        pol = policy.lower()
        (OUT / pol).mkdir(parents=True, exist_ok=True)
        stem = f"{pol}/{cat}_{order}_seed{seed}" + ("_rep" if rep else "")
        out_csv = OUT / f"{stem}.csv"
        banktrace = OUT / f"{stem}_banktrace.csv"
        done += 1
        if banktrace.exists():
            log(f"SKIP {stem}  ({done}/{len(all_jobs)})")
            continue
        stream = STREAM_ROOT / cat / "production_runs" / f"{cat}_{order}_eps_0_seed_{seed}" / "stream.json"
        if not stream.exists():
            log(f"ERROR missing stream {stream}")
            continue
        cfg = {
            "category": cat,
            "memory_policy": policy,
            "calibration": "none",
            "diagnostic_bank_trace": True,
            "checkpoint_path": CHECKPOINT,
            "reservoir_seed": int(seed),  # fixed per cell -> base/repeat reproducible
        }
        t0 = time.time()
        RareCLIPWrapper().run(
            stream_path=str(stream),
            dataset_root="data/mvtec_ad",
            output_csv=str(out_csv),
            config=cfg,
        )
        ran += 1
        log(f"DONE {stem} in {time.time() - t0:.0f}s  ({done}/{len(all_jobs)})")
    log(f"Policy-swap complete: ran {ran}, accounted {done}/{len(all_jobs)} in {(time.time() - t_all) / 3600:.2f}h")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate1", action="store_true")
    main(gate1=ap.parse_args().gate1)
