#!/usr/bin/env python3
"""Part B control runner: 3 cats x seeds 0-4 x {none,same,cross} = 45 cells.
RareCLIP default/SCS, VisA checkpoint, scores only (within-target-block AUROC).
Absolute paths; resumable (skip existing); MVTec/VisA/concat artifacts untouched."""
from __future__ import annotations
import sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from experiments.baselines.rareclip import RareCLIPWrapper
STREAMS=ROOT/"results/latest/paper_candidate/control_visa_streams"
OUT=ROOT/"results/latest/paper_candidate/diagnostic_rareclip_scs_control_visa"
LOG=OUT/"control_run.log"
CATS=["candle","macaroni1","macaroni2"]; SEEDS=range(5); KINDS=["none","same","cross"]
def log(m):
    line=f"[{time.strftime('%H:%M:%S')}] {m}"; print(line,flush=True)
    with LOG.open("a") as f: f.write(line+"\n")
def main(only=None):
    OUT.mkdir(parents=True,exist_ok=True)
    jobs=[(c,s,k) for c in CATS for s in SEEDS for k in KINDS]
    if only: jobs=[j for j in jobs if j in only]
    log(f"Control run: {len(jobs)} cells")
    t0=time.time(); ran=done=0
    for c,s,k in jobs:
        stem=f"{c}_{k}_seed{s}"; out=OUT/f"{stem}.csv"; done+=1
        if out.exists(): log(f"SKIP {stem}"); continue
        stream=STREAMS/f"{stem}"/"stream.json"
        if not stream.exists(): log(f"MISSING {stream}"); continue
        cfg={"category":c,"memory_policy":"default/SCS","calibration":"none",
             "diagnostic_bank_trace":False,"checkpoint_path":"external/RareCLIP/weights/visa_pretrained.pth"}
        t=time.time()
        RareCLIPWrapper().run(stream_path=str(stream),dataset_root="data/visa/1cls",output_csv=str(out),config=cfg)
        ran+=1; log(f"DONE {stem} in {time.time()-t:.0f}s ({done}/{len(jobs)})")
    log(f"Control run complete: ran {ran}, accounted {done}/{len(jobs)} in {(time.time()-t0)/3600:.2f}h")
if __name__=="__main__":
    import argparse; ap=argparse.ArgumentParser(); ap.add_argument("--gate1",action="store_true"); a=ap.parse_args()
    main(only=[("candle",0,k) for k in KINDS] if a.gate1 else None)
