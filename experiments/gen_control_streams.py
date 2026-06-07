#!/usr/bin/env python3
"""Generate + validate the same-category-fill CONTROL streams (Part B).
3 categories x seeds 0-4 x {none(baseline), same, cross} = 45 streams.
Target block = 50 normal + 25 anomaly (identical across the 3 conditions);
normal-only prefix length 50 (same-cat vs cross-cat differ only in category identity)."""
import sys, json, os; sys.path.insert(0, "experiments")
import make_streams as ms
DR="data/visa/1cls"; CATS=["candle","macaroni1","macaroni2"]; SEEDS=range(5)
OUT="results/latest/paper_candidate/control_visa_streams"
os.makedirs(OUT, exist_ok=True)
def others(c): return [x for x in CATS if x!=c]
n=0
for c in CATS:
    for s in SEEDS:
        for kind in ("none","same","cross"):
            p=ms.build_prefix_target_stream(dataset_root=DR,target_category=c,prefix_kind=kind,
                other_categories=others(c),dataset="VisA",seed=s,target_normal=50,target_anom=25,prefix_len=50)
            d=f"{OUT}/{c}_{kind}_seed{s}"; os.makedirs(d,exist_ok=True)
            ms.write_stream(p,f"{d}/stream.json"); n+=1
print(f"wrote {n} control streams (expect 45)")

# ===== VALIDATION =====
def load(c,kind,s): return json.load(open(f"{OUT}/{c}_{kind}_seed{s}/stream.json"))
issues=[]
for c in CATS:
    for s in SEEDS:
        st={k:load(c,k,s) for k in ("none","same","cross")}
        # (1) prefix lengths: none=0, same=cross=50  [CRITICAL assert]
        pl={k:st[k]['metadata']['prefix_length'] for k in st}
        if not (pl['none']==0 and pl['same']==50 and pl['cross']==50):
            issues.append(f"{c} s{s}: prefix lengths {pl} != (0,50,50)")
        # (2) target block identical across the 3 conditions (image_path set + order)
        def tgt(k): return [(it['image_path'],it['label']) for it in st[k]['items'] if it['block_index']==1]
        if not (tgt('none')==tgt('same')==tgt('cross')):
            issues.append(f"{c} s{s}: target block differs across conditions")
        # target composition: 50 normal + 25 anomaly
        t=tgt('none'); na=sum(1 for _,l in t if l==1)
        if not (len(t)==75 and na==25): issues.append(f"{c} s{s}: target {len(t)} imgs / {na} anom != 75/25")
        for k in st:
            items=st[k]['items']; paths=[it['image_path'] for it in items]
            # (3) no-duplicate within stream
            if len(set(paths))!=len(paths): issues.append(f"{c} {k} s{s}: DUP paths")
            # (4) labels 0/1; prefix normal-only; prefix↔target disjoint
            if set(it['label'] for it in items)-{0,1}: issues.append(f"{c} {k} s{s}: bad labels")
            pref=[it for it in items if it['block_index']==0]
            if any(it['label']!=0 for it in pref): issues.append(f"{c} {k} s{s}: prefix not normal-only")
            ptp=set(it['image_path'] for it in pref); ttp=set(it['image_path'] for it in items if it['block_index']==1)
            if ptp & ttp: issues.append(f"{c} {k} s{s}: prefix/target overlap")
            # cross prefix must come from the 2 OTHER categories; same from target cat
            if k=="cross":
                pc=set(it['category'] for it in pref)
                if pc!=set(others(c)): issues.append(f"{c} cross s{s}: prefix cats {pc} != others {set(others(c))}")
            if k=="same":
                pc=set(it['category'] for it in pref)
                if pc!={c}: issues.append(f"{c} same s{s}: prefix cats {pc} != {{{c}}}")
print("VALIDATION:", "ALL PASS" if not issues else f"{len(issues)} ISSUES")
for i in issues[:10]: print("  -",i)
# show one example
ex=load("candle","cross",0)['metadata']
print("example candle_cross_seed0:", {k:ex[k] for k in ('prefix_length','target_length','target_normal_count','target_anom_count','applied_stream_length')})
