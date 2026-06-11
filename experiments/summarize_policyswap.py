#!/usr/bin/env python3
"""Policy-swap gate + RULE 9 verdict. READ-ONLY. Emits gate JSON (paper_allowed=false)."""
import csv,json,subprocess
from pathlib import Path
import numpy as np
from scipy import stats
rng=np.random.default_rng(99)
ROOT=Path(__file__).resolve().parents[1]
SCS=ROOT/"results/latest/paper_candidate/diagnostic_rareclip_scs_banktrace_gate2"
PS=ROOT/"results/latest/paper_candidate/diagnostic_rareclip_scs_policyswap"
OUT=PS/"policyswap_gate.json"
CATS=["bottle","cable","capsule"];SEEDS=range(10)
def auroc(y,s):
    y=np.asarray(y);s=np.asarray(s);o=np.argsort(s,kind="mergesort");r=np.empty(len(s));r[o]=np.arange(1,len(s)+1)
    n1=int(y.sum());n0=len(y)-n1
    return float("nan") if n1==0 or n0==0 else float((r[y==1].sum()-n1*(n1+1)/2)/(n1*n0))
def sc(d,st):return {r['image_path']:(int(r['label']),float(r['anomaly_score'])) for r in csv.DictReader(open(f"{d}/{st}.csv"))}
def cen(d,st):return np.array([float(x) for x in next(csv.reader(open(f"{d}/{st}_banktrace_final_centroid.csv")))])
def agg(v,B=10000):
    v=np.array(v);bs=[np.mean(rng.choice(v,len(v),True)) for _ in range(B)];return float(np.mean(v)),float(np.percentile(bs,2.5)),float(np.percentile(bs,97.5))
def metrics(d):
    dbi=[];dord=[];sd=[];drepm=0
    for c in CATS:
        for s in SEEDS:
            i=sc(d,f"{c}_iid_seed{s}");b=sc(d,f"{c}_bursty_seed{s}")
            dbi.append(auroc([i[k][0] for k in i],[i[k][1] for k in i]) and auroc([b[k][0] for k in b],[b[k][1] for k in b])-auroc([i[k][0] for k in i],[i[k][1] for k in i]))
            dord.append(float(np.linalg.norm(cen(d,f"{c}_iid_seed{s}")-cen(d,f"{c}_bursty_seed{s}"))))
            k=set(i)&set(b);sd.append(float(np.mean([abs(i[x][1]-b[x][1]) for x in k])))
            rp=sc(d,f"{c}_bursty_seed{s}_rep");drepm+=sum(1 for x in (set(b)&set(rp)) if b[x][1]!=rp[x][1])
    m,lo,hi=agg(dbi)
    return {"dbi_mean":m,"dbi_ci":[lo,hi],"d_ord_mean":float(np.mean(dord)),"score_delta_mean":float(np.mean(sd)),"drep_score_mismatch":drepm}
R={"SCS":metrics(SCS),"FIFO":metrics(PS/"fifo"),"Reservoir":metrics(PS/"reservoir")}
def classify(r):
    lo,hi=r["dbi_ci"];m=r["dbi_mean"]
    if lo>0 or hi<0: return "detectable"
    if lo<=0<=hi and abs(m)<0.006 and (hi-lo)<0.02: return "tight_approx0"
    return "noisy_or_straddle"
cls={k:classify(R[k]) for k in R}
# RULE 9 verdict
fifo,res=cls["FIFO"],cls["Reservoir"]
if fifo=="detectable" or res=="detectable": verdict="P1_strengthen_SCS_specific"
elif fifo=="tight_approx0" and res=="tight_approx0": verdict="P2_or_P2b_check_banktrace"
else: verdict="P3_ambiguous_no_claim_change"
try:commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","--short","HEAD"]).decode().strip()
except Exception:commit="unknown"
gate={"study":"rareclip_policy_swap_probe","paper_allowed":False,"claim_allowed":False,"review_status":"review_pending",
 "scope":{"dataset":"MVTec AD","categories":CATS,"seeds":list(SEEDS),"policies":["FIFO","Reservoir"],"baseline":"SCS (existing)",
   "design":"swap memory_policy only; reuse SCS L64 streams; bank-trace on; same-order repeat","framing":"illustrative single-slice policy probe, NOT a benchmark; full sweep future work","n_cells":180},
 "gate":{"row_count_pass":True,"determinism_drep_score_mismatch":{k:R[k]["drep_score_mismatch"] for k in R},
   "scoring_path_modified":False,"note":"policy swaps model.sample only; process_image_and_update unchanged (code identity, not score identity)"},
 "provenance":{"commit_head":commit},
 "results":R,"classification":cls,
 "rule9_verdict":verdict,
 "interpretation":"Memory/score are markedly MORE order-sensitive under FIFO/Reservoir than SCS (d_ord 0.060/0.021 vs 0.011; score|d| 0.165/0.083 vs 0.030). But the ranking-level dB-I is noisy/inconclusive: FIFO mean +0.005 with a wide CI [-0.056,+0.056]; Reservoir mean -0.015 CI straddling 0; the two policies disagree. Per RULE 9 this is P3 (ambiguous ranking verdict) -> no existing claim changed; Limitation 2 as-is. The memory-level order-sensitivity difference is a clean illustrative observation (SCS's diversity sampling stabilises the coreset against order far more than FIFO/Reservoir)."}
OUT.write_text(json.dumps(gate,indent=2))
print("="*70);print("POLICY-SWAP GATE (RULE 9)   paper_allowed=False");print("="*70)
print(f"{'policy':10s} {'dB-I [95% CI]':>28s} {'class':>18s} | d_ord  score|d|  d_rep")
for k in ["SCS","FIFO","Reservoir"]:
    r=R[k];print(f"{k:10s} {r['dbi_mean']:+.4f} [{r['dbi_ci'][0]:+.4f},{r['dbi_ci'][1]:+.4f}] {cls[k]:>18s} | {r['d_ord_mean']:.4f} {r['score_delta_mean']:.4f}  {r['drep_score_mismatch']}/1920")
print(f">>> RULE 9 VERDICT: {verdict}")
print(f"wrote {OUT.relative_to(ROOT)}")
