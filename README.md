# ZIAD Protocol: Streaming Industrial Anomaly Detection Evaluation

This repository implements a reproducible protocol for **streaming industrial
anomaly detection evaluation**. It evaluates zero-shot and training-light
detectors when test images arrive as streams rather than as a static offline
benchmark.

The canonical experiment reference is [`docs/experiment-prd.md`](docs/experiment-prd.md).
The final paper artifact is `paper/paper.pdf`, which may only reference `results/latest/`.

## Overview

**Goal.** Benchmark zero-shot and training-light industrial anomaly detectors
under streaming conditions, then produce paper-ready evidence only after an
explicit review gate.

**Datasets.**

- MVTec AD
- VisA

**Baselines.**

- PatchCore
- WinCLIP
- AnomalyCLIP
- RareCLIP

**Experiment axes.**

- stream type: `iid`, `bursty`
- contamination epsilon: currently `0`, `0.05` for compact full-P0 validation
- calibration: `none`, `temperature_scaling`
- memory policy: `default/SCS`, `Reservoir` for PatchCore/RareCLIP;
  `default/no-memory` for WinCLIP/AnomalyCLIP

**Current status.** P0 smoke coverage is complete and compact full-P0
production-validation has completed `24/24` aggregate steps. The outputs are
validated pipeline evidence, not final paper results. All current full-P0
artifacts keep `paper_allowed=false`, `claim_allowed=false`, and
`review_status=not_reviewed`.

Paper-candidate execution is now category-sharded under a separate output root,
`results/latest/paper_candidate/`. Each shard uses
`run_tier=paper_candidate`, `candidate_scope=category_shard`,
`execution_mode=production`, `paper_allowed=false`, `claim_allowed=false`, and
`review_status=review_pending`. Category shards are still not full paper
results. The four paper-candidate shard sets,
`MVTec AD × WinCLIP × default/no-memory × none` and
`MVTec AD × AnomalyCLIP × default/no-memory × none`, and
`MVTec AD × RareCLIP × default/SCS × none`, and
`MVTec AD × PatchCore × default/SCS × none`, are complete for all 15 MVTec AD
categories at stream length `64` and seeds `0,1,2`, closing the current minimum
MVTec AD four-baseline comparison slice. The VisA paper-candidate comparison now
includes `VisA × WinCLIP × default/no-memory × none`,
`VisA × AnomalyCLIP × default/no-memory × none`,
`VisA × RareCLIP × default/SCS × none`, and
`VisA × PatchCore × default/SCS × none`, each complete for all 12 VisA
categories at the same stream length and seeds. The combined MVTec AD + VisA
paper-candidate comparison table has also been generated for the calibration
`none` slice. A no-inference stream/epsilon breakdown now exposes the same
candidate rows by `iid` versus `bursty` and epsilon `0` versus `0.05`; these
remain review-pending candidate evidence, not final paper results.

## Result Artifacts

Compact portfolio-friendly artifacts are tracked under `results/latest/`.
Per-run streams, scores, configs, caches, model outputs, datasets, and external
baseline clones are intentionally gitignored.

Full-P0 production-validation artifacts:

- `results/latest/p0_full/execution_plan.json`
- `results/latest/p0_full/manifest.json`
- `results/latest/p0_full/validation_report.json`
- `results/latest/tables/p0_full_validation_summary.csv`
- `results/latest/tables/p0_full_validation_summary.tex`

Paper-candidate pilot artifacts are generated locally under
`results/latest/paper_candidate/` and are intentionally separate from
`results/latest/p0_full/`. They are gitignored by default because they are
larger per-run outputs.

Current paper-candidate shard summary:

- `results/latest/paper_candidate/mvtec_ad/winclip/default_no_memory/none/category_summary.csv`
- `results/latest/paper_candidate/mvtec_ad/winclip/default_no_memory/none/category_summary.json`
- `results/latest/paper_candidate/mvtec_ad/anomalyclip/default_no_memory/none/category_summary.csv`
- `results/latest/paper_candidate/mvtec_ad/anomalyclip/default_no_memory/none/category_summary.json`
- `results/latest/paper_candidate/mvtec_ad/rareclip/default_scs/none/category_summary.csv`
- `results/latest/paper_candidate/mvtec_ad/rareclip/default_scs/none/category_summary.json`
- `results/latest/paper_candidate/mvtec_ad/patchcore/default_scs/none/category_summary.csv`
- `results/latest/paper_candidate/mvtec_ad/patchcore/default_scs/none/category_summary.json`
- `results/latest/paper_candidate/visa/winclip/default_no_memory/none/category_summary.csv`
- `results/latest/paper_candidate/visa/winclip/default_no_memory/none/category_summary.json`
- `results/latest/paper_candidate/visa/anomalyclip/default_no_memory/none/category_summary.csv`
- `results/latest/paper_candidate/visa/anomalyclip/default_no_memory/none/category_summary.json`
- `results/latest/paper_candidate/visa/rareclip/default_scs/none/category_summary.csv`
- `results/latest/paper_candidate/visa/rareclip/default_scs/none/category_summary.json`
- `results/latest/paper_candidate/visa/patchcore/default_scs/none/category_summary.csv`
- `results/latest/paper_candidate/visa/patchcore/default_scs/none/category_summary.json`

Current MVTec AD paper-candidate baseline comparison:

- `results/latest/paper_candidate/mvtec_ad/baseline_comparison_none.csv`
- `results/latest/paper_candidate/mvtec_ad/baseline_comparison_none.json`
- `results/latest/tables/paper_candidate_mvtec_baseline_comparison_none.tex`

Current VisA paper-candidate baseline comparison:

- `results/latest/paper_candidate/visa/baseline_comparison_none.csv`
- `results/latest/paper_candidate/visa/baseline_comparison_none.json`
- `results/latest/tables/paper_candidate_visa_baseline_comparison_none.tex`

Current combined paper-candidate baseline comparison:

- `results/latest/paper_candidate/baseline_comparison_all_datasets_none.csv`
- `results/latest/paper_candidate/baseline_comparison_all_datasets_none.json`
- `results/latest/tables/paper_candidate_baseline_comparison_all_datasets_none.tex`
- `results/latest/paper_candidate/stream_epsilon_breakdown_none.csv`
- `results/latest/paper_candidate/stream_epsilon_breakdown_none.json`
- `results/latest/tables/paper_candidate_stream_epsilon_breakdown_none.tex`
- `results/latest/paper_candidate/baseline_ranking_summary.json`
- `results/latest/tables/paper_candidate_ranking_summary.tex`
- `results/latest/paper_candidate/metric_audit_report.json`
- `results/latest/tables/paper_candidate_metric_audit_summary.tex`
- `results/latest/figures/paper_candidate_accuracy_latency_tradeoff.png`
- `results/latest/figures/paper_candidate_accuracy_latency_tradeoff.pdf`

Appendix stream-length sensitivity scaffold:

- `experiments/configs/sensitivity/stream_length.yaml`
- `results/latest/sensitivity/stream_length/manifest.json`
- `results/latest/sensitivity/stream_length/execution_plan.json`
- `results/latest/sensitivity/stream_length/summary.csv`
- `results/latest/sensitivity/stream_length/summary.json`
- `results/latest/tables/stream_length_sensitivity_summary.tex`

This scaffold is intentionally small: MVTec AD only, PatchCore and WinCLIP,
categories `bottle`, `cable`, `capsule`, stream lengths `64`, `128`, `256`,
`iid`/`bursty`, epsilon `0`/`0.05`, seeds `0,1,2`, and calibration `none`.
It is an appendix sanity check, not a main paper result.

Current tiny pilot coverage:

- `MVTec AD × WinCLIP × bottle × stream_length=64`: complete in the current
  local summary, 12 rows
- `MVTec AD × WinCLIP × bottle × stream_length=256`: complete, 12 rows

The `stream_length=128` shard was run in an earlier local pilot, but its
ignored aggregate output is not present in the current results tree. Do not
claim a 64/128/256 trend until that shard is regenerated under an explicit
inference request and reviewed. The current pilot shards remain
`paper_allowed=false`, `claim_allowed=false`, and
`review_status=review_pending`.

Runtime documentation for claim-promotion review:

- `docs/runtime_environment.md`

Smoke and paper-input artifacts:

- `results/latest/tables/p0_smoke_summary.csv`
- `results/latest/tables/p0_smoke_summary_manifest.json`
- `results/latest/tables/p0_smoke_summary.tex`
- `results/latest/tables/paper_input_contract.json`

The validation report summarizes each of the 24 full-P0 aggregate steps:
dataset, baseline, memory policy, calibration, row count, expected row count,
category count, status values, stream length, sampler setting, closed paper
gates, and aggregate output paths.

## Reproducibility

Regenerate the full-P0 report without inference:

```bash
python3 experiments/p0_full_report.py
```

Build the paper-candidate skeleton without inference:

```bash
python3 experiments/paper_candidate.py \
  --config experiments/configs/paper_candidate/compact.yaml \
  --manifest results/latest/paper_candidate/manifest.json \
  --execution-plan results/latest/paper_candidate/execution_plan.json
```

Run one paper-candidate category shard:

```bash
python3 experiments/run_paper_candidate_step.py \
  --plan results/latest/paper_candidate/execution_plan.json \
  --step-id mvtec_ad:winclip:default_no_memory:none \
  --category cable \
  --output-root results/latest/paper_candidate/mvtec_ad/winclip/default_no_memory/none/cable
```

The runner skips a completed category shard only when that shard's
`metrics.csv`, `manifest.json`, and `crd_lite.csv` exist and pass the closed
gate and row-count checks. A completed category shard is not accepted as a
full-category paper result.

Build the stream-length sensitivity scaffold without inference:

```bash
python3 experiments/stream_length_sensitivity.py
python3 experiments/run_stream_length_sensitivity_step.py \
  --step-id mvtec_ad:winclip:default_no_memory:none:bottle:len_128 \
  --dry-run
python3 experiments/summarize_stream_length_sensitivity.py
```

Sensitivity outputs live under `results/latest/sensitivity/stream_length/`.
They remain appendix/sanity-check artifacts with `paper_allowed=false` and
`claim_allowed=false`.

Summarize a completed MVTec AD paper-candidate category-shard set:

```bash
python3 experiments/summarize_paper_candidate_categories.py \
  --plan results/latest/paper_candidate/execution_plan.json \
  --step-id mvtec_ad:anomalyclip:default_no_memory:none \
  --output-root results/latest/paper_candidate/mvtec_ad/anomalyclip/default_no_memory/none
```

Generate the current MVTec AD paper-candidate baseline comparison without
running inference:

```bash
python3 experiments/summarize_paper_candidate_baselines.py
```

Generate the current VisA paper-candidate baseline comparison without running
inference:

```bash
python3 experiments/summarize_paper_candidate_baselines.py \
  --input-root results/latest/paper_candidate/visa \
  --baseline winclip:default_no_memory \
  --baseline anomalyclip:default_no_memory \
  --baseline rareclip:default_scs \
  --baseline patchcore:default_scs \
  --output-csv results/latest/paper_candidate/visa/baseline_comparison_none.csv \
  --output-json results/latest/paper_candidate/visa/baseline_comparison_none.json \
  --output-tex results/latest/tables/paper_candidate_visa_baseline_comparison_none.tex
```

Generate the combined MVTec AD + VisA paper-candidate baseline comparison
without running inference:

```bash
python3 experiments/summarize_paper_candidate_all_datasets.py
```

Generate the review-pending paper-candidate ranking summary and
accuracy-latency trade-off figure without running inference:

```bash
python3 experiments/render_paper_candidate_analysis.py
```

Generate the review-pending stream/epsilon breakdown without running inference:

```bash
python3 experiments/summarize_paper_candidate_stream_epsilon.py
```

Audit the combined paper-candidate metric table before claim promotion:

```bash
python3 experiments/audit_paper_candidate_metrics.py
```

Generate the paper-candidate promotion readiness report without changing any
paper or claim gates:

```bash
python3 scripts/check_paper_promotion_readiness.py
```

The checklist is documented in
[`docs/paper_promotion_checklist.md`](docs/paper_promotion_checklist.md). The
expected current status is `ready_for_promotion=false` until runtime/timing
semantics and manual reviewer approval are complete.

Check paper source readiness for the integrated ACCV/LNCS template:

```bash
python3 scripts/check_paper_template_readiness.py
```

Template migration notes are documented in
[`docs/accv_template_migration.md`](docs/accv_template_migration.md). The
repository vendors the unpacked template under `paper/template/` and copies the
required build-time class/style files into `paper/` for the existing build path.

Dry-run the completed full-P0 execution plan:

```bash
python3 experiments/run_p0_execution_plan.py \
  --plan results/latest/p0_full/execution_plan.json --dry-run
```

Run the test suite:

```bash
python3 -m unittest discover -v
python3 -m compileall experiments tests
bash scripts/build_paper.sh
git diff --check
```

## Limitations

- Current full-P0 outputs are production-validation artifacts, not paper
  results.
- Current paper-candidate outputs are category shards, not a complete reviewed
  paper matrix.
- Validation-scale stream lengths are present (`2`, plus earlier MVTec
  PatchCore validation aggregates at `20`).
- Paper-candidate stream length is `64`, with seeds `0,1,2`; only
  `MVTec AD × WinCLIP × default/no-memory × none`,
  `MVTec AD × AnomalyCLIP × default/no-memory × none`,
  `MVTec AD × RareCLIP × default/SCS × none`, and
  `MVTec AD × PatchCore × default/SCS × none`, plus
  `VisA × WinCLIP × default/no-memory × none`,
  `VisA × AnomalyCLIP × default/no-memory × none`, and
  `VisA × RareCLIP × default/SCS × none`, and
  `VisA × PatchCore × default/SCS × none`, have complete category-shard
  coverage so far.
- The current MVTec AD paper-candidate baseline comparison includes WinCLIP,
  AnomalyCLIP, RareCLIP, and PatchCore. It is still review-pending candidate
  evidence, not a promoted paper result.
- The current VisA paper-candidate baseline comparison includes WinCLIP,
  AnomalyCLIP, RareCLIP, and PatchCore. It is still review-pending candidate
  evidence, not a promoted paper result.
- The combined MVTec AD + VisA paper-candidate comparison includes both
  4-baseline dataset slices and ranking summaries. It is still
  `review_pending`, with `paper_allowed=false` and `claim_allowed=false`.
- The stream/epsilon breakdown is generated from existing category-shard
  metrics and exposes `iid`/`bursty` and epsilon `0`/`0.05` groups without
  running new inference. It is still review-pending candidate evidence.
- Stream-length sensitivity has only a tiny WinCLIP/bottle pilot in the current
  local summary at lengths `64` and `256`; the intended intermediate `128`
  aggregate is not present locally, and the full bounded sensitivity grid has
  not been run. Treat it as preliminary appendix evidence only.
- The generated paper-candidate accuracy-latency figure and ranking table are
  analysis artifacts only. They are included in the input contract but are not
  promoted paper results.
- The paper-candidate metric audit checks missing values, NaN/Inf values,
  negative latency, row/dataset/baseline counts, and closed paper/claim gates;
  a passing audit does not promote claims.
- Runtime documentation is incomplete for final latency claims: the original
  device path, model-loading scope, batch settings, and timing granularity must
  still be confirmed before promotion.
- PatchCore validation uses bounded `sampler_percentage=0.001`.
- Paper-candidate config records and uses PatchCore `sampler_percentage=0.1`.
- Paper promotion requires non-validation stream length, reviewed sampler and
  memory settings, row-count/category-count checks, no NaN/Inf metrics, and
  manual review.
- Do not change `paper_allowed` or `claim_allowed` without a separate reviewed
  promotion step.

## Experiment Setup (Smoke First)

```text
1. Place datasets under data/        (gitignored — download MVTec AD / VisA locally)
2. Clone baselines under external/   (gitignored — current URLs/commits pinned in baselines.yaml)
3. Run smoke:  bash scripts/run_smoke.sh
4. Run a mini-matrix: bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml
5. Build paper: make paper
```

- `data/` and `external/` are gitignored. Real datasets and baseline clones must be placed locally.
- Baseline repo URLs and commit hashes are pinned from current local clones (see `experiments/configs/baselines.yaml`).
- Use `bash scripts/setup_baselines.sh` to see per-baseline clone slot status and pinned clone commands.
- See [`docs/experiment-prd.md`](docs/experiment-prd.md) for the full experiment PRD including gates, schema, and P0 scope.

---

## Paper Pipeline

The final paper artifact:

## Build the paper

```bash
bash scripts/build_paper.sh
# or
make paper
```

The build script first refreshes generated tables under `results/latest/tables/`,
then produces `paper/paper.pdf`. If no LaTeX engine is installed, it writes a
dependency-free placeholder PDF that preserves the TODO/no-fake-results rule.

## Refresh paper-facing tables only

```bash
bash scripts/render_paper_tables.sh
# or
make paper-tables
```

This renders checked result CSVs into LaTeX tables. With no arguments it
refreshes the compact P0 smoke summary, the full-P0 production-validation
summary, the MVTec quick-sweep smoke table, and the MVTec/VisA
stream/epsilon/calibration smoke tables for PatchCore, WinCLIP, AnomalyCLIP,
and RareCLIP. All generated tables are explicitly marked non-final and
paper-ineligible because `paper_allowed` remains `false`.

The compact summary artifacts are:

- `results/latest/tables/p0_smoke_summary.csv`
- `results/latest/tables/p0_smoke_summary_manifest.json`
- `results/latest/tables/p0_smoke_summary.tex`
- `results/latest/p0_full/validation_report.json`
- `results/latest/tables/p0_full_validation_summary.csv`
- `results/latest/tables/p0_full_validation_summary.tex`
- `results/latest/tables/paper_input_contract.json`

The compact summary includes the `memory_policy` axis. Current smoke evidence
contains `default/SCS` plus measured `MVTec AD × RareCLIP × FIFO`,
`MVTec AD × RareCLIP × Reservoir`/`Prototype-EMA`,
`VisA × RareCLIP × FIFO`/`Reservoir`/`Prototype-EMA`, and
`VisA × PatchCore × FIFO`/`Reservoir`/`Prototype-EMA` plus
`MVTec AD × PatchCore × FIFO`/`Reservoir`/`Prototype-EMA`
memory-policy shards. Memory-policy smoke shard coverage is complete, but
these remain paper-ineligible until reviewed full P0 runs exist.

`paper_input_contract.json` is the current paper table/figure input contract:
it lists generated table sources, row counts, source manifests, whether a table
is included by `paper/paper.tex`, and keeps `claim_allowed=false` while the
results are smoke-only.

## Refresh placeholder P0 outputs

```bash
bash scripts/run_p0.sh
# or
make p0
```

This refreshes placeholder files under `results/latest/`; it does not run real model inference and does not create measured findings.

## Plan current P0 shards

```bash
python3 experiments/p0_shards.py plan experiments/configs/p0.yaml \
  --output results/latest/p0_shards/manifest.json
python3 experiments/p0_shards.py execution-plan experiments/configs/p0.yaml \
  --output results/latest/p0_shards/execution_plan.json
python3 experiments/p0_shards.py verify results/latest/p0_shards/manifest.json \
  --require-outputs
python3 experiments/run_p0_execution_plan.py --dry-run
# or
bash scripts/run_p0_execution_plan.sh --dry-run
```

This writes an orchestration manifest that maps the intended P0 matrix onto the
currently implemented all-category smoke matrix runners. It also records which
temperature-scaling calibration shards are implemented separately from the base
stream/epsilon shards. It creates no metrics, keeps `paper_allowed=false`, and
records unsupported or missing dimensions explicitly.

`execution_plan.json` is a restartable local execution manifest over those
shards. It fixes the order as base stream/epsilon shards, then memory-policy
shards, then calibration shards, records aggregate outputs for skip/resume, and
keeps `claim_allowed=false`.

The execution-plan runner consumes that manifest. It skips a step when all
declared aggregate outputs exist, the aggregate manifest keeps
`paper_allowed=false`, `claim_allowed` is not true, and the aggregate metrics row
count matches the step's expected smoke run count. Missing outputs make a step
pending; without `--dry-run`, the runner executes the step command and validates
again. Validation failures stop immediately.

Useful scoped runs:

```bash
python3 experiments/run_p0_execution_plan.py --dry-run --step 0
python3 experiments/run_p0_execution_plan.py --dry-run \
  --step mvtec_ad_rareclip_stream_epsilon_smoke:base
python3 experiments/run_p0_execution_plan.py --dry-run --start-index 0 --end-index 2
```

Do not run the full execution plan as paper evidence. All current outputs remain
smoke evidence with `paper_allowed=false` until reviewed full P0 results are
explicitly promoted in a separate step.

## Plan compact full P0 skeleton

```bash
python3 experiments/p0_full.py \
  --config experiments/configs/p0_full/compact.yaml \
  --manifest results/latest/p0_full/manifest.json \
  --execution-plan results/latest/p0_full/execution_plan.json
python3 experiments/run_p0_execution_plan.py \
  --plan results/latest/p0_full/execution_plan.json --dry-run
python3 experiments/run_p0_full_step.py \
  --plan results/latest/p0_full/execution_plan.json --step 0 --dry-run
python3 experiments/run_p0_full_step.py \
  --plan results/latest/p0_full/execution_plan.json \
  --step-id mvtec_ad:winclip:default_no_memory:none \
  --output-root results/latest/p0_full/mvtec_ad/winclip/default_no_memory/none \
  --validation-mode lightweight --stream-length 20
python3 experiments/run_p0_full_step.py \
  --plan results/latest/p0_full/execution_plan.json \
  --step-id mvtec_ad:winclip:default_no_memory:none \
  --output-root results/latest/p0_full/mvtec_ad/winclip/default_no_memory/none \
  --stream-length 2
python3 experiments/run_p0_full_step.py \
  --plan results/latest/p0_full/execution_plan.json \
  --step-id mvtec_ad:winclip:default_no_memory:temperature_scaling \
  --output-root results/latest/p0_full/mvtec_ad/winclip/default_no_memory/temperature_scaling \
  --stream-length 2
python3 experiments/run_p0_full_step.py \
  --plan results/latest/p0_full/execution_plan.json \
  --step-id visa:winclip:default_no_memory:none \
  --output-root results/latest/p0_full/visa/winclip/default_no_memory/none \
  --stream-length 2
python3 experiments/run_p0_full_step.py \
  --plan results/latest/p0_full/execution_plan.json \
  --step-id visa:winclip:default_no_memory:temperature_scaling \
  --output-root results/latest/p0_full/visa/winclip/default_no_memory/temperature_scaling \
  --stream-length 2
python3 experiments/run_p0_full_step.py \
  --plan results/latest/p0_full/execution_plan.json \
  --step-id mvtec_ad:anomalyclip:default_no_memory:none \
  --output-root results/latest/p0_full/mvtec_ad/anomalyclip/default_no_memory/none \
  --stream-length 2
```

This defines a separate full-P0 planning tier without running inference. Smoke
orchestration remains under `results/latest/p0_shards/`; reviewed full-P0
skeleton artifacts and future full outputs live under `results/latest/p0_full/`.
Smoke outputs must not satisfy full-P0 outputs.

The current compact full-P0 skeleton has deterministic aggregate matrix count `288`:
MVTec AD/VisA, PatchCore/WinCLIP/AnomalyCLIP/RareCLIP, iid/bursty, epsilon
`0/0.05`, calibration `none/temperature_scaling`, explicit seeds `0/1/2`,
and memory policies `default/SCS,Reservoir` for PatchCore/RareCLIP plus
`default/no-memory` for WinCLIP/AnomalyCLIP. It groups those runs into 24
pending aggregate steps. Production validation is category-aware: MVTec steps
expect 15 categories and 180 rows, VisA steps expect 12 categories and 144
rows, for production matrix count `3888`. The execution-plan runner can dry-run
this skeleton. Current production-validation has completed 24/24 aggregate
steps using the bounded validation settings below; this is not paper evidence.

The single-step full-P0 executor resolves one step by id or index, enforces
`results/latest/p0_full/` output paths, and dry-runs without creating outputs.
The bounded `--validation-mode lightweight` path runs one selected aggregate
step as single-category validation and writes only under `results/latest/p0_full/`.
Lightweight outputs are not accepted as completed production outputs; a
completed production aggregate manifest must declare `execution_mode=production`
and match the production row count.

The current production-validation outputs live under
`results/latest/p0_full/{dataset}/{baseline}/{memory_policy}/{calibration}/`.
All 24 aggregate steps are complete: MVTec steps have 180 rows across 15
categories, VisA steps have 144 rows across 12 categories, every aggregate row
uses status `measured_full_p0`, and full-P0 dry-run reports `skipped=24` and
`pending=0`. The validation report records stream-length values from the
aggregate manifests; current values are validation-only (`2`, with earlier
MVTec PatchCore validation aggregates at `20`). PatchCore validation also uses
`sampler_percentage=0.001`. They are not reviewed paper results.

Generate the validation report and paper-promotion checklist:

```bash
python3 experiments/p0_full_report.py
```

This writes:

- `results/latest/p0_full/validation_report.json`
- `results/latest/tables/p0_full_validation_summary.csv`
- `results/latest/tables/p0_full_validation_summary.tex`

Paper promotion requires a separate reviewed run. Do not promote validation
runs; require a non-validation stream length, reviewed paper sampler/memory
settings, row-count and category-count checks, no NaN/Inf metric values, and
manual review before changing `paper_allowed` or `claim_allowed`.

Full-P0 skeleton gates stay closed by default:
`run_tier=p0_full`, `execution_mode=production` for production-complete outputs,
`paper_allowed=false`, `claim_allowed=false`, and `review_status=not_reviewed`.

## Run a measured mini-matrix smoke

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml
```

Mini-matrix outputs are measured pipeline evidence but remain paper-ineligible:
`paper_allowed` must stay `false` until full reviewed P0 results exist.

The aggregate mini-matrix step also writes a CRD-lite smoke summary such as
`results/latest/mini_matrix/crd_lite_winclip_bottle.csv`. CRD-lite is derived
from epsilon-0 AUROC/AUPR drops and is diagnostic until full P0 review.

## Run the AnomalyCLIP bottle smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_anomalyclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_anomalyclip.csv \
  --latest-run results/latest/latest_run_anomalyclip.json \
  --output results/latest/metrics_anomalyclip.csv \
  --manifest results/latest/manifest_anomalyclip.json
```

This uses the local AnomalyCLIP checkpoint and the upstream image-level
`text_probs[:, 0, 1]` anomaly score on the project stream order. It remains
smoke evidence with `paper_allowed=false`.

## Run the RareCLIP bottle smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_rareclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_rareclip.csv \
  --latest-run results/latest/latest_run_rareclip.json \
  --output results/latest/metrics_rareclip.csv \
  --manifest results/latest/manifest_rareclip.json
```

This uses the local RareCLIP MVTec checkpoint and upstream
`process_image_and_update(..., update=True)` image-level anomaly score on the
project stream order. It remains smoke evidence with `paper_allowed=false`.

## Run the AnomalyCLIP bottle mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/anomalyclip_mini_matrix.yaml
```

This runs AnomalyCLIP on MVTec AD bottle for `iid/bursty × ε 0/0.01/0.05`,
then writes aggregate metrics and a CRD-lite smoke summary under
`results/latest/mini_matrix/`. It is measured smoke evidence only.

## Run the RareCLIP bottle mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/rareclip_mini_matrix.yaml
```

This runs RareCLIP on MVTec AD bottle for `iid/bursty × ε 0/0.01/0.05`,
then writes aggregate metrics and a CRD-lite smoke summary under
`results/latest/mini_matrix/`. It uses CPU single-image online inference in the
current local setup and remains paper-ineligible.

## Run the VisA WinCLIP smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_winclip.csv \
  --latest-run results/latest/latest_run_visa_winclip.json \
  --output results/latest/metrics_visa_winclip.csv \
  --manifest results/latest/manifest_visa_winclip.json
```

This validates the VisA adapter on `data/visa/1cls/candle` with a length-20,
iid, epsilon-zero stream. It is measured smoke evidence only and keeps
`paper_allowed=false`.

## Run the VisA PatchCore smoke

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_visa_patchcore.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_patchcore.csv \
  --latest-run results/latest/latest_run_visa_patchcore.json \
  --output results/latest/metrics_visa_patchcore.csv \
  --manifest results/latest/manifest_visa_patchcore.json
```

This validates PatchCore on `data/visa/1cls/candle` with the same length-20,
iid, epsilon-zero stream contract. The smoke config uses `sampler: random`
because the default approximate greedy coreset path is valid but much slower on
CPU. Outputs remain paper-ineligible with `paper_allowed=false`.

## Run the VisA WinCLIP mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_winclip_mini_matrix.yaml
```

This runs WinCLIP on VisA candle for `iid/bursty × ε 0/0.01/0.05`, length-20
streams. It writes aggregate metrics and CRD-lite smoke summaries under
`results/latest/visa_mini_matrix/`; these outputs are still paper-ineligible.

## Run the VisA PatchCore mini-matrix

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_patchcore_mini_matrix.yaml
```

This runs PatchCore on VisA candle for `iid/bursty × ε 0/0.01/0.05`,
length-20 streams. It uses `baseline_options.sampler: random` to keep the smoke
runtime bounded, then writes aggregate metrics and CRD-lite smoke summaries
under `results/latest/visa_patchcore_mini_matrix/`; these outputs are still
paper-ineligible.

## Run the VisA full-category WinCLIP smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_winclip.sh
```

This expands VisA coverage to all 12 local `data/visa/1cls` categories for
WinCLIP with iid, epsilon-zero, length-20 streams. It writes aggregate metrics
and CRD-lite smoke summaries under
`results/latest/visa_full_category_sweep_winclip/`; these outputs are still
smoke evidence with `paper_allowed=false`.

## Run the VisA full-category AnomalyCLIP smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_anomalyclip.sh
```

This uses the same all-12-category VisA smoke shape for AnomalyCLIP with iid,
epsilon-zero, length-20 streams. It is CPU single-image inference and remains
smoke evidence with `paper_allowed=false`.

## Run the VisA full-category PatchCore smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_patchcore.sh
```

This uses the same all-12-category VisA smoke shape for PatchCore with iid,
epsilon-zero, length-20 streams. It uses `baseline_options.sampler: identity` to
avoid the slow upstream coreset subsampling step; `run_smoke.sh` forwards these
baseline-specific YAML options into the wrapper. The aggregate output remains
smoke evidence with `paper_allowed=false`.

## Run the VisA full-category RareCLIP smoke sweep

```bash
bash scripts/run_visa_full_category_sweep_rareclip.sh
```

This uses the same all-12-category VisA smoke shape for RareCLIP with iid,
epsilon-zero, length-20 streams. It exercises the online memory update path and
remains smoke evidence with `paper_allowed=false`.

## Run the VisA full-category stream/epsilon matrices

```bash
bash scripts/run_visa_full_category_stream_matrix_winclip.sh
bash scripts/run_visa_full_category_stream_matrix_winclip_temperature.sh
bash scripts/run_visa_full_category_stream_matrix_anomalyclip.sh
bash scripts/run_visa_full_category_stream_matrix_anomalyclip_temperature.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_fifo.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_prototype_ema.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_reservoir.sh
bash scripts/run_visa_full_category_stream_matrix_patchcore_temperature.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_fifo.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_prototype_ema.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_reservoir.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip_temperature.sh
```

Each command runs one baseline over all 12 local VisA categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. The aggregate outputs live
under `results/latest/visa_full_category_stream_matrix_<baseline>/` and remain
smoke evidence with `paper_allowed=false`. The temperature runners add the
`calibration none/temperature_scaling` axis and write to separate
`results/latest/visa_full_category_stream_matrix_<baseline>_temperature/`
roots. They materialize from the corresponding measured non-temperature stream
matrix and apply deterministic calibration postprocessing, so they do not rerun
baseline inference for calibration variants.

The RareCLIP FIFO, Reservoir, and Prototype-EMA runners plus the PatchCore FIFO,
Reservoir, and Prototype-EMA runners are memory-policy shards over the same all-category VisA stream/epsilon
smoke shape. They write to separate
`results/latest/visa_full_category_stream_matrix_<baseline>_<policy>/` roots
and are tracked separately from the default/SCS and calibration shards.

## Run a category quick sweep

```bash
bash scripts/run_category_quick_sweep.sh experiments/configs/category_quick_sweep.yaml
```

This runs a small PatchCore/WinCLIP × bottle/capsule/hazelnut smoke sweep to
catch category-specific failures before full P0. It is measured but still
paper-ineligible.

## Run the MVTec full-category WinCLIP smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep.sh
```

This expands the category coverage to all 15 MVTec AD categories for WinCLIP
with iid, epsilon-zero, length-20 streams. It is still smoke evidence, not a
full P0 result.

## Run the MVTec full-category PatchCore smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep_patchcore.sh
```

This uses the same all-category smoke shape for PatchCore. It exercises the
train/good setup and stream-ordered offline scoring path across all MVTec
categories. It is still smoke evidence and remains paper-ineligible.

## Run the MVTec full-category AnomalyCLIP smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep_anomalyclip.sh
```

This uses the same all-category smoke shape for AnomalyCLIP with iid,
epsilon-zero, length-20 streams. It is CPU single-image inference and remains
smoke evidence with `paper_allowed=false`.

## Run the MVTec full-category RareCLIP smoke sweep

```bash
bash scripts/run_mvtec_full_category_sweep_rareclip.sh
```

This uses the same all-category smoke shape for RareCLIP with iid,
epsilon-zero, length-20 streams. It is CPU single-image online inference and
remains smoke evidence with `paper_allowed=false`.

## Run the MVTec full-category WinCLIP stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_winclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_winclip_temperature.sh
```

This runs WinCLIP across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. It writes aggregate metrics
and CRD-lite summaries only; generated per-run details remain ignored. The
temperature runner adds the `calibration none/temperature_scaling` axis by
materializing from measured non-temperature scores.

## Run the MVTec full-category AnomalyCLIP stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_anomalyclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_anomalyclip_temperature.sh
```

This runs AnomalyCLIP across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. The temperature runner adds
the `calibration none/temperature_scaling` axis without rerunning inference. It
is CPU single-image inference and remains smoke evidence with
`paper_allowed=false`.

## Run the MVTec full-category RareCLIP stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_rareclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_fifo.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_reservoir.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_prototype_ema.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip_temperature.sh
```

This runs RareCLIP across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. The temperature runner adds
the `calibration none/temperature_scaling` axis without rerunning inference. It
exercises the online memory update path. The FIFO runner is the separate
RareCLIP memory-policy shard over the same stream/epsilon shape, and the
Reservoir runner records the corresponding bounded reservoir memory-policy
shard. The Prototype-EMA runner records the bounded prototype memory-policy
shard. All outputs
remain smoke evidence with `paper_allowed=false`.

## Run the MVTec full-category PatchCore stream matrix

```bash
bash scripts/run_mvtec_full_category_stream_matrix_patchcore.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_fifo.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_reservoir.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_prototype_ema.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore_temperature.sh
```

This runs PatchCore across all 15 MVTec AD categories for
`iid/bursty × ε 0/0.01/0.05`, length-20 streams. It uses the train/good
offline batch-amortized smoke path and an ignored local fitted-model cache to
avoid rebuilding the same per-category support index for every stream condition.
The FIFO, Reservoir, and Prototype-EMA runners record separate bounded
feature-bank memory-policy shards and remain smoke evidence with
`paper_allowed=false`.
The temperature runner adds the `calibration none/temperature_scaling` axis
without rerunning inference. It remains smoke evidence with `paper_allowed=false`.

## Current result contract

- `results/latest/latest_run.json`: one current run/status summary.
- `results/latest/manifest.json`: one current list of paper-facing result files.
- `results/latest/scores.csv`: score CSV contract, currently placeholder.
- `results/latest/metrics.csv`: metric CSV contract, currently placeholder.

If `results/latest/manifest.json` is not `final` with `paper_allowed: true`, the Results section must stay TODO/placeholder.

## P0 scope

- Datasets: MVTec AD, VisA
- Streams: iid, bursty
- Prevalence: 0.05
- Contamination ε: 0, 0.01, 0.05
- Baselines: RareCLIP, PatchCore, WinCLIP, AnomalyCLIP
- Memory policies for RareCLIP/PatchCore: default/SCS, FIFO, Reservoir, Prototype-EMA
- Calibration: none, temperature scaling
- Metrics: Image AUROC, AUPR, ECE, latency, CRD-lite

## Result authenticity rule

Do not place fabricated metrics in `paper/paper.md`, `paper/paper.tex`, or `paper/paper.pdf`. Missing or unrun results must remain TODO/placeholder.
