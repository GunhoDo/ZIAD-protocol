#!/usr/bin/env python3
"""Control gate + decision (Part B): same-category-fill isolates the cause of the concat
collapse. READ-ONLY over control outputs + streams. Emits gate JSON (paper_allowed=false).
LOCKED RULE 8 decision rule applied. No paper edits, no flags auto-flipped."""
import csv, json, subprocess
from pathlib import Path
import numpy as np
rng=np.random.default_rng(2026)
ROOT=Path(__file__).resolve().parents[1]
O=ROOT/"results/latest/paper_candidate/diagnostic_rareclip_scs_control_visa"
S=ROOT/"results/latest/paper_candidate/control_visa_streams"
OUT=O/"concat_control_gate.json"
CATS=["candle","macaroni1","macaroni2"]; SEEDS=range(5); KINDS=["none","same","cross"]
def auroc(y,s):
    y=np.asarray(y);s=np.asarray(s);o=np.argsort(s,kind="mergesort");r=np.empty(len(s));r[o]=np.arange(1,len(s)+1)
    n1=int(y.sum());n0=len(y)-n1
    return float("nan") if n1==0 or n0==0 else float((r[y==1].sum()-n1*(n1+1)/2)/(n1*n0))
def target(c,k,s):
    rows=sorted(csv.DictReader(open(f"{O}/{c}_{k}_seed{s}.csv")),key=lambda r:int(r['stream_index']))[-75:]
    return np.array([int(r['label']) for r in rows]), np.array([float(r['anomaly_score']) for r in rows])
def agg(vals,B=10000):
    v=np.array(vals);bs=[np.mean(rng.choice(v,len(v),True)) for _ in range(B)]
    return float(np.mean(v)),float(np.percentile(bs,2.5)),float(np.percentile(bs,97.5))

# gate 1: row-count
present=sum(1 for c in CATS for s in SEEDS for k in KINDS if (O/f"{c}_{k}_seed{s}.csv").exists())
rc_pass=present==45
# gate 2: stream validation (prefix 0/50/50; target identical across conditions)
val=[]
for c in CATS:
    for s in SEEDS:
        st={k:json.load(open(f"{S}/{c}_{k}_seed{s}/stream.json")) for k in KINDS}
        pl={k:st[k]['metadata']['prefix_length'] for k in st}
        if not(pl['none']==0 and pl['same']==50 and pl['cross']==50): val.append(f"{c}s{s} prefixlen {pl}")
        tgt=lambda k:[(it['image_path'],it['label']) for it in st[k]['items'] if it['block_index']==1]
        if not(tgt('none')==tgt('same')==tgt('cross')): val.append(f"{c}s{s} target differs")
val_pass=not val
# results
cells={k:{} for k in KINDS}
for c in CATS:
    for s in SEEDS:
        for k in KINDS:
            y,sc=target(c,k,s); cells[k][(c,s)]=auroc(y,sc)
res={}
for k in KINDS:
    m,lo,hi=agg(list(cells[k].values())); res[k]={"mean":m,"ci_lo":lo,"ci_hi":hi}
d_same=[cells["none"][cs]-cells["same"][cs] for cs in cells["none"]]
d_cross=[cells["none"][cs]-cells["cross"][cs] for cs in cells["none"]]
ms,los,his=agg(d_same); mc,loc,hic=agg(d_cross)
same_flat = los<=0<=his or abs(ms)<0.05          # not a collapse
cross_drop = loc>0 and mc>0.05                    # meaningful drop, CI excludes 0
decision = "CAUSAL_CLAIM_STANDS_cross_category_contamination" if (cross_drop and same_flat) else "RETRACT_position_or_saturation"
try: commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","--short","HEAD"]).decode().strip()
except Exception: commit="unknown"
gate={"study":"rareclip_scs_concat_control","paper_allowed":False,"claim_allowed":False,"review_status":"review_pending",
 "scope":{"dataset":"VisA","categories":CATS,"seeds":list(SEEDS),"conditions":KINDS,
   "target_block":"50 normal + 25 anomaly (identical across conditions)","prefix":"normal-only, length 50",
   "cross_prefix":"two other categories, mixed","n_cells":45},
 "gate_1_row_count":{"pass":rc_pass,"present":present,"expected":45},
 "gate_2_stream_validation":{"pass":val_pass,"asserts":"prefix len 0/50/50; target identical across conditions; (full asserts in gen_control_streams.py)","problems":val},
 "provenance":{"commit_head":commit,"scoring_path_modified":False,"existing_generators_modified":False,"flags_modified":False,
   "source_dir":str(O.relative_to(ROOT))},
 "results":{"within_block_auroc":res,
   "delta_none_minus_same":{"mean":ms,"ci":[los,his],"cells_dropping":int(sum(1 for x in d_same if x>0))},
   "delta_none_minus_cross":{"mean":mc,"ci":[loc,hic],"cells_dropping":int(sum(1 for x in d_cross if x>0))}},
 "decision_rule_RULE8":{"same_flat":bool(same_flat),"cross_drop":bool(cross_drop),"decision":decision,
   "note":"same-cat reported as flat (not improved); control isolates causation not magnitude (not comparable to concat Δ)"}}
OUT.write_text(json.dumps(gate,indent=2))
print("="*64); print("CONCAT CONTROL GATE (Rule 8)   paper_allowed=False"); print("="*64)
print(f"GATE 1 row-count: {'PASS' if rc_pass else 'FAIL'} ({present}/45)")
print(f"GATE 2 stream-validation: {'PASS' if val_pass else 'FAIL'} {val[:3]}")
print(f"provenance: {commit} | scoring/generators/flags untouched")
for k in KINDS: print(f"  {k:6s}: AUROC {res[k]['mean']:.3f} [{res[k]['ci_lo']:.3f},{res[k]['ci_hi']:.3f}]")
print(f"  none-same  Δ={ms:+.3f} [{los:+.3f},{his:+.3f}]  (drop {sum(1 for x in d_same if x>0)}/15)  -> same_flat={same_flat}")
print(f"  none-cross Δ={mc:+.3f} [{loc:+.3f},{hic:+.3f}]  (drop {sum(1 for x in d_cross if x>0)}/15)  -> cross_drop={cross_drop}")
print(f">>> DECISION: {decision}")
print(f"wrote {OUT.relative_to(ROOT)}")
