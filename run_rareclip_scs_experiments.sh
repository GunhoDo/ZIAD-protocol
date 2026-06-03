#!/bin/bash
# RareCLIP SCS ΔB-I power-resolved replication — VisA pcb3/pcb4 slice.
#
# Design: VisA pcb3/pcb4 (201 test images each; applied ~201 at requested L=256),
# seeds 0–9, ε=0, at L=64 and L=256, with OPCLite K=8 as positive control
# at each length in the same batch.
#
# L=64:  both OPC and RC expected non-significant (low-power condition)
# L=256: OPC expected significant (proves detectability); RC result is the finding

set -e
LOGFILE="run_rareclip_scs_experiments.log"
exec > >(tee -a "$LOGFILE") 2>&1

echo "=== VisA pcb3/pcb4 experiment start at $(date -u) ==="
echo "Slice: pcb3 pcb4 | Seeds: 0-9 | ε=0 | L=64 and L=256"

PLAN_OPC64="results/latest/paper_candidate/diagnostic_opc_visa_pcb_sl64/execution_plan.json"
PLAN_OPC256="results/latest/paper_candidate/diagnostic_opc_visa_pcb_sl256/execution_plan.json"
PLAN_RC64="results/latest/paper_candidate/diagnostic_rareclip_scs_visa_pcb_sl64/execution_plan.json"
PLAN_RC256="results/latest/paper_candidate/diagnostic_rareclip_scs_visa_pcb_sl256/execution_plan.json"
OPC_STEP="visa:onlinepatchcorelite:fifo:none"
RC_STEP="visa:rareclip:default_scs:none"

# ── Positive control @ L=64 ─────────────────────────────────────────────────
echo "--- [POSITIVE CONTROL] OPCLite K=8 @ L=64 ---"
for cat in pcb3 pcb4; do
    echo "[opc64] $cat at $(date -u)"
    python3 experiments/run_paper_candidate_step.py \
        --plan "$PLAN_OPC64" --step "$OPC_STEP" --category "$cat"
    echo "[opc64] done: $cat"
done

# ── RareCLIP @ L=64 ─────────────────────────────────────────────────────────
echo "--- [TARGET] RareCLIP default/SCS @ L=64 ---"
for cat in pcb3 pcb4; do
    echo "[rc64] $cat at $(date -u)"
    python3 experiments/run_paper_candidate_step.py \
        --plan "$PLAN_RC64" --step "$RC_STEP" --category "$cat"
    echo "[rc64] done: $cat"
done

# ── Positive control @ L=256 ────────────────────────────────────────────────
echo "--- [POSITIVE CONTROL] OPCLite K=8 @ L=256 ---"
for cat in pcb3 pcb4; do
    echo "[opc256] $cat at $(date -u)"
    python3 experiments/run_paper_candidate_step.py \
        --plan "$PLAN_OPC256" --step "$OPC_STEP" --category "$cat"
    echo "[opc256] done: $cat"
done

# ── RareCLIP @ L=256 ────────────────────────────────────────────────────────
echo "--- [TARGET] RareCLIP default/SCS @ L=256 ---"
for cat in pcb3 pcb4; do
    echo "[rc256] $cat at $(date -u)"
    python3 experiments/run_paper_candidate_step.py \
        --plan "$PLAN_RC256" --step "$RC_STEP" --category "$cat"
    echo "[rc256] done: $cat"
done

echo "=== Experiment complete at $(date -u) ==="
