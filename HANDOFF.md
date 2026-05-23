# HANDOFF — ZIAD 논문 구현 현재 상태

최종 갱신: 2026-05-21
프로젝트: Streaming Zero-Shot Industrial Anomaly Detection with CLIP / ZIAD Protocol

## 0. 절대 규칙

- `AGENTS.md`와 `docs/experiment-prd.md`가 canonical reference다.
- baseline URL/commit hash를 새로 지어내지 말 것. `experiments/configs/baselines.yaml`의 local clone 기준을 사용한다.
- fake metric 금지. placeholder는 `placeholder_not_measured`, 실제 측정은 `measured`/`measured_smoke`만 사용한다.
- 논문 게이트는 아직 닫힘: 모든 현재 산출물은 `paper_allowed=false` 유지.
- `.omx/`는 planning history이며 소스 오브 트루스가 아니다.

## 1. 현재 논문 구현 진척

### 완료

- PatchCore 실제 wrapper 구현 완료: `experiments/baselines/patchcore.py`
  - upstream: `external/patchcore-inspection`
  - train source: `train/good`
  - stream/eval source: `test/*`
  - scoring mode: `stream_ordered_offline`
  - latency semantics: `offline_batch_amortized`
  - fitted-model cache: `results/latest/patchcore_model_cache/**` (gitignored)
  - stream inference is restricted to stream-referenced test images, not the full test split
- WinCLIP 실제 wrapper 구현 완료: `experiments/baselines/winclip.py`
  - upstream: `external/WinClip`
  - stream/eval source: project stream JSON only
  - upstream full-split dataset loader는 사용하지 않음
  - scoring mode: zero-shot WinCLIP anomaly map max → image-level score
  - CPU smoke 경로는 upstream fp16 기본값을 fp32로 보정
- AnomalyCLIP 실제 wrapper 구현 완료: `experiments/baselines/anomalyclip.py`
  - upstream: `external/AnomalyCLIP`
  - checkpoint: `external/AnomalyCLIP/checkpoints/9_12_4_multiscale/epoch_15.pth`
  - stream/eval source: project stream JSON only
  - upstream full-split dataset loader는 사용하지 않음
  - scoring mode: upstream image-level `text_probs[:, 0, 1]` anomaly probability
  - CLIP ViT-L/14@336px backbone cache: `external/AnomalyCLIP/.cache/clip`
- RareCLIP 실제 wrapper 구현 완료: `experiments/baselines/rareclip.py`
  - upstream: `external/RareCLIP`
  - checkpoint: `external/RareCLIP/weights/mvtec_pretrained.pth`
  - stream/eval source: project stream JSON only
  - upstream full-split dataset loader는 사용하지 않음
  - scoring mode: upstream `process_image_and_update(..., update=True)` image-level anomaly score
  - CLIP ViT-L/14@336px backbone cache는 기존 AnomalyCLIP cache를 `external/cache/ViT-L-14-336px.pt`로 재사용
- deterministic MVTec/VisA stream generator 구현 완료: `experiments/make_streams.py`
  - fields: `stream_index,image_path,label,category,source_split,anomaly_type`
  - no duplicate samples
  - label integrity 유지
  - requested prevalence/epsilon을 정확히 못 맞추면 가장 가까운 feasible ratio 선택
  - 실제 applied stats와 warnings를 stream metadata에 기록
  - `iid`, `bursty` 지원
  - `bursty`는 anomaly가 contiguous block(s)에 들어가도록 보장
  - VisA는 `data/visa/1cls/<category>/test/{good,bad}` 또는 `data/visa/<category>/test/{good,bad}`를 같은 schema로 index한다.
- evaluator 구현 완료: `experiments/evaluate.py`
  - AUROC, AUPR, diagnostic ECE, mean latency 계산
  - CRD-lite는 아직 `NA`
  - unknown status 거부
- config-driven smoke runner 구현 완료: `scripts/run_smoke.sh [config]`
  - per-config outputs 지원
- baseline-parametric mini-matrix runner 구현 완료:
  - helper: `experiments/mini_matrix.py`
  - runner: `scripts/run_baseline_mini_matrix.sh`
  - PatchCore compatibility wrapper: `scripts/run_patchcore_mini_matrix.sh`
  - `iid/bursty × epsilon 0/0.01/0.05`, MVTec AD bottle, baseline config driven
- CRD-lite smoke summary 구현 완료: `experiments/mini_matrix.py`
  - epsilon 0 대비 현재 epsilon의 `image_auroc`/`aupr` signed drop 평균
  - positive는 contamination degradation, 0은 measured drop 없음, negative는 smoke metric improvement
  - full P0 전까지 pipeline diagnostic이며 paper-ready metric 아님
- MVTec category quick sweep 구현 완료:
  - helper: `experiments/category_sweep.py`
  - runner: `scripts/run_category_quick_sweep.sh`
  - config: `experiments/configs/category_quick_sweep.yaml`
  - PatchCore/WinCLIP × bottle/capsule/hazelnut × iid × ε=0, length=20
- paper-facing smoke evidence table pipeline 구현 완료:
  - renderer: `experiments/render_paper_tables.py`
  - runner: `scripts/render_paper_tables.sh`
  - Make target: `make paper-tables`
  - output: `results/latest/tables/smoke_evidence_summary.tex`
  - `scripts/build_paper.sh`가 paper build 전에 table renderer를 호출함
  - table caption/comment에 non-final, paper-ineligible, `paper_allowed=false`가 명시됨
- MVTec full-category WinCLIP smoke sweep 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_sweep_winclip.yaml`
  - runner: `scripts/run_mvtec_full_category_sweep.sh`
  - categories: all 15 MVTec AD categories
  - baseline: WinCLIP only
  - stream/epsilon: iid, ε=0, length=20
  - generated details/configs are ignored; combined aggregate files remain trackable
- MVTec full-category PatchCore smoke sweep 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_sweep_patchcore.yaml`
  - runner: `scripts/run_mvtec_full_category_sweep_patchcore.sh`
  - categories: all 15 MVTec AD categories
  - baseline: PatchCore only
  - stream/epsilon: iid, ε=0, length=20
  - generated details/configs are ignored; combined aggregate files remain trackable
- MVTec full-category AnomalyCLIP smoke sweep 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_sweep_anomalyclip.yaml`
  - runner: `scripts/run_mvtec_full_category_sweep_anomalyclip.sh`
  - categories: all 15 MVTec AD categories
  - baseline: AnomalyCLIP only
  - stream/epsilon: iid, ε=0, length=20
  - generated details/configs are ignored; combined aggregate files remain trackable
- MVTec full-category RareCLIP smoke sweep 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_sweep_rareclip.yaml`
  - runner: `scripts/run_mvtec_full_category_sweep_rareclip.sh`
  - categories: all 15 MVTec AD categories
  - baseline: RareCLIP only
  - stream/epsilon: iid, ε=0, length=20
  - generated details/configs are ignored; combined aggregate files remain trackable
- MVTec full-category WinCLIP stream/epsilon matrix 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_stream_matrix_winclip.yaml`
  - runner: `scripts/run_mvtec_full_category_stream_matrix_winclip.sh`
  - categories: all 15 MVTec AD categories
  - baseline: WinCLIP only
  - stream/epsilon: `iid`, `bursty` × ε=`0`, `0.01`, `0.05`, length=20
  - generated details/configs are ignored; combined aggregate files remain trackable
- MVTec full-category PatchCore stream/epsilon matrix 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_stream_matrix_patchcore.yaml`
  - runner: `scripts/run_mvtec_full_category_stream_matrix_patchcore.sh`
  - categories: all 15 MVTec AD categories
  - baseline: PatchCore only
  - stream/epsilon: `iid`, `bursty` × ε=`0`, `0.01`, `0.05`, length=20
  - generated details/configs and fitted-model cache are ignored; combined aggregate files remain trackable
- MVTec full-category AnomalyCLIP stream/epsilon matrix 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_stream_matrix_anomalyclip.yaml`
  - runner: `scripts/run_mvtec_full_category_stream_matrix_anomalyclip.sh`
  - categories: all 15 MVTec AD categories
  - baseline: AnomalyCLIP only
  - stream/epsilon: `iid`, `bursty` × ε=`0`, `0.01`, `0.05`, length=20
  - generated details/configs are ignored; combined aggregate files remain trackable
- MVTec full-category RareCLIP stream/epsilon matrix 구성/실행 완료:
  - config: `experiments/configs/mvtec_full_category_stream_matrix_rareclip.yaml`
  - runner: `scripts/run_mvtec_full_category_stream_matrix_rareclip.sh`
  - categories: all 15 MVTec AD categories
  - baseline: RareCLIP only
  - stream/epsilon: `iid`, `bursty` × ε=`0`, `0.01`, `0.05`, length=20
  - generated details/configs are ignored; combined aggregate files remain trackable
- VisA WinCLIP smoke 구성 완료:
  - config: `experiments/configs/smoke_visa_winclip.yaml`
  - dataset root: `data/visa/1cls`
  - category: `candle`
  - stream/epsilon: `iid`, ε=`0`, length=20
  - outputs remain paper-ineligible with `paper_allowed=false`
- VisA WinCLIP mini-matrix 구성 완료:
  - config: `experiments/configs/visa_winclip_mini_matrix.yaml`
  - dataset root: `data/visa/1cls`
  - category: `candle`
  - stream/epsilon: `iid`, `bursty` × ε=`0`, `0.01`, `0.05`, length=20
  - generated per-run configs/details are ignored; aggregate files remain trackable
- VisA standalone smoke configs 구성 완료:
  - WinCLIP bursty: `experiments/configs/smoke_visa_winclip_bursty.yaml`
  - AnomalyCLIP iid: `experiments/configs/smoke_visa_anomalyclip.yaml`
  - RareCLIP iid: `experiments/configs/smoke_visa_rareclip.yaml`
  - PatchCore iid: `experiments/configs/smoke_visa_patchcore.yaml`
  - dataset root: `data/visa/1cls`
  - category: `candle`
  - stream/epsilon: ε=`0`, length=20
  - outputs remain paper-ineligible with `paper_allowed=false`
- VisA full-category WinCLIP smoke sweep 구성 완료:
  - config: `experiments/configs/visa_full_category_sweep_winclip.yaml`
  - runner: `scripts/run_visa_full_category_sweep_winclip.sh`
  - dataset root: `data/visa/1cls`
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - baseline: WinCLIP only
  - stream/epsilon: `iid`, ε=`0`, length=20
  - generated per-run configs/details are ignored; combined aggregate files remain trackable
- VisA full-category AnomalyCLIP smoke sweep 구성 완료:
  - config: `experiments/configs/visa_full_category_sweep_anomalyclip.yaml`
  - runner: `scripts/run_visa_full_category_sweep_anomalyclip.sh`
  - dataset root: `data/visa/1cls`
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - baseline: AnomalyCLIP only
  - stream/epsilon: `iid`, ε=`0`, length=20
  - generated per-run configs/details are ignored; combined aggregate files remain trackable
- VisA full-category RareCLIP smoke sweep 구성 완료:
  - config: `experiments/configs/visa_full_category_sweep_rareclip.yaml`
  - runner: `scripts/run_visa_full_category_sweep_rareclip.sh`
  - dataset root: `data/visa/1cls`
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - baseline: RareCLIP only
  - stream/epsilon: `iid`, ε=`0`, length=20
  - generated per-run configs/details are ignored; combined aggregate files remain trackable
- VisA full-category stream/epsilon matrix 구성 완료:
  - WinCLIP config: `experiments/configs/visa_full_category_stream_matrix_winclip.yaml`
  - AnomalyCLIP config: `experiments/configs/visa_full_category_stream_matrix_anomalyclip.yaml`
  - RareCLIP config: `experiments/configs/visa_full_category_stream_matrix_rareclip.yaml`
  - runners: `scripts/run_visa_full_category_stream_matrix_{winclip,anomalyclip,rareclip}.sh`
  - dataset root: `data/visa/1cls`
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - stream/epsilon: `iid`, `bursty` × ε=`0`, `0.01`, `0.05`, length=20
  - generated per-run configs/details are ignored; combined aggregate files remain trackable

### 실제 실행 완료

- Commit: `d21401a Enable honest PatchCore stream smoke execution`
- Bursty smoke 실행 완료:
  - config: `experiments/configs/smoke_bursty.yaml`
  - stream: `results/latest/stream_smoke_bursty.json`
  - scores: `results/latest/scores_bursty.csv`
  - metrics: `results/latest/metrics_bursty.csv`
  - result: 20 measured rows, contiguous anomaly block `[1]`, `paper_allowed=false`
- PatchCore mini-matrix 6 runs 실행 완료:
  - config: `experiments/configs/patchcore_mini_matrix.yaml`
  - aggregate metrics: `results/latest/mini_matrix/metrics_patchcore_bottle.csv`
  - CRD-lite summary: `results/latest/mini_matrix/crd_lite_patchcore_bottle.csv`
  - aggregate manifest: `results/latest/mini_matrix/manifest_patchcore_bottle.json`
  - rows: 6 measured_smoke rows
  - stream types: `iid`, `bursty`
  - epsilon: `0.0`, `0.01`, `0.05`
  - `paper_allowed=false`
- WinCLIP iid smoke 실행 완료:
  - config: `experiments/configs/smoke_winclip.yaml`
  - stream: `results/latest/stream_smoke_winclip.json`
  - scores: `results/latest/scores_winclip.csv`
  - metrics: `results/latest/metrics_winclip.csv`
  - latest run: `results/latest/latest_run_winclip.json`
  - manifest: `results/latest/manifest_winclip.json`
  - result: 20 measured rows, `status=measured_smoke`, `paper_allowed=false`
- WinCLIP mini-matrix 6 runs 실행 완료:
  - config: `experiments/configs/winclip_mini_matrix.yaml`
  - command: `bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml`
  - aggregate metrics: `results/latest/mini_matrix/metrics_winclip_bottle.csv`
  - CRD-lite summary: `results/latest/mini_matrix/crd_lite_winclip_bottle.csv`
  - aggregate manifest: `results/latest/mini_matrix/manifest_winclip_bottle.json`
  - rows: 6 measured_smoke rows
  - stream types: `iid`, `bursty`
  - epsilon: `0.0`, `0.01`, `0.05`
  - `paper_allowed=false`
- MVTec category quick sweep 실행 완료:
  - config: `experiments/configs/category_quick_sweep.yaml`
  - command: `bash scripts/run_category_quick_sweep.sh experiments/configs/category_quick_sweep.yaml`
  - aggregate metrics: `results/latest/category_quick_sweep/metrics_mvtec_category_quick_sweep.csv`
  - CRD-lite summary: `results/latest/category_quick_sweep/crd_lite_mvtec_category_quick_sweep.csv`
  - manifest: `results/latest/category_quick_sweep/manifest_mvtec_category_quick_sweep.json`
  - rows: 6 measured_smoke rows
  - categories: `bottle`, `capsule`, `hazelnut`
  - baselines: `PatchCore`, `WinCLIP`
  - stream/epsilon: `iid`, `0.0`
  - `paper_allowed=false`
- Paper table renderer 실행 완료:
  - command: `bash scripts/render_paper_tables.sh`
  - generated table: `results/latest/tables/smoke_evidence_summary.tex`
  - source metrics: `results/latest/category_quick_sweep/metrics_mvtec_category_quick_sweep.csv`
  - source manifest: `results/latest/category_quick_sweep/manifest_mvtec_category_quick_sweep.json`
  - `paper_allowed=false` 유지
- MVTec full-category WinCLIP smoke sweep 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_sweep.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_sweep_winclip/metrics_mvtec_full_category_sweep_winclip.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_sweep_winclip/crd_lite_mvtec_full_category_sweep_winclip.csv`
  - manifest: `results/latest/mvtec_full_category_sweep_winclip/manifest_mvtec_full_category_sweep_winclip.json`
  - rows: 15 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `WinCLIP`
  - stream/epsilon: `iid`, `0.0`
  - `toothbrush` emitted the expected feasible-ratio warning due sample-count constraints
  - `paper_allowed=false`
- MVTec full-category PatchCore smoke sweep 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_sweep_patchcore.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_sweep_patchcore/metrics_mvtec_full_category_sweep_patchcore.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_sweep_patchcore/crd_lite_mvtec_full_category_sweep_patchcore.csv`
  - manifest: `results/latest/mvtec_full_category_sweep_patchcore/manifest_mvtec_full_category_sweep_patchcore.json`
  - rows: 15 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `PatchCore`
  - stream/epsilon: `iid`, `0.0`
  - `toothbrush` emitted the expected feasible-ratio warning due sample-count constraints
  - `paper_allowed=false`
- AnomalyCLIP iid smoke 실행 완료:
  - config: `experiments/configs/smoke_anomalyclip.yaml`
  - stream: `results/latest/stream_smoke_anomalyclip.json`
  - scores: `results/latest/scores_anomalyclip.csv`
  - metrics: `results/latest/metrics_anomalyclip.csv`
  - latest run: `results/latest/latest_run_anomalyclip.json`
  - manifest: `results/latest/manifest_anomalyclip.json`
  - result: 20 measured rows, `status=measured_smoke`, `paper_allowed=false`
- RareCLIP iid smoke 실행 완료:
  - config: `experiments/configs/smoke_rareclip.yaml`
  - stream: `results/latest/stream_smoke_rareclip.json`
  - scores: `results/latest/scores_rareclip.csv`
  - metrics: `results/latest/metrics_rareclip.csv`
  - latest run: `results/latest/latest_run_rareclip.json`
  - manifest: `results/latest/manifest_rareclip.json`
  - result: 20 measured rows, `status=measured_smoke`, `paper_allowed=false`
- AnomalyCLIP mini-matrix 6 runs 실행 완료:
  - config: `experiments/configs/anomalyclip_mini_matrix.yaml`
  - command: `bash scripts/run_baseline_mini_matrix.sh experiments/configs/anomalyclip_mini_matrix.yaml`
  - aggregate metrics: `results/latest/mini_matrix/metrics_anomalyclip_bottle.csv`
  - CRD-lite summary: `results/latest/mini_matrix/crd_lite_anomalyclip_bottle.csv`
  - aggregate manifest: `results/latest/mini_matrix/manifest_anomalyclip_bottle.json`
  - rows: 6 measured_smoke rows
  - stream types: `iid`, `bursty`
  - epsilon: `0.0`, `0.01`, `0.05`
  - ε=`0.01` emitted the expected feasible-ratio warning in iid and bursty runs
  - `paper_allowed=false`
- RareCLIP mini-matrix 6 runs 실행 완료:
  - config: `experiments/configs/rareclip_mini_matrix.yaml`
  - command: `bash scripts/run_baseline_mini_matrix.sh experiments/configs/rareclip_mini_matrix.yaml`
  - aggregate metrics: `results/latest/mini_matrix/metrics_rareclip_bottle.csv`
  - CRD-lite summary: `results/latest/mini_matrix/crd_lite_rareclip_bottle.csv`
  - aggregate manifest: `results/latest/mini_matrix/manifest_rareclip_bottle.json`
  - rows: 6 measured_smoke rows
  - stream types: `iid`, `bursty`
  - epsilon: `0.0`, `0.01`, `0.05`
  - ε=`0.01` emitted the expected feasible-ratio warning in iid and bursty runs
  - `paper_allowed=false`
- MVTec full-category AnomalyCLIP smoke sweep 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_sweep_anomalyclip.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_sweep_anomalyclip/metrics_mvtec_full_category_sweep_anomalyclip.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_sweep_anomalyclip/crd_lite_mvtec_full_category_sweep_anomalyclip.csv`
  - manifest: `results/latest/mvtec_full_category_sweep_anomalyclip/manifest_mvtec_full_category_sweep_anomalyclip.json`
  - rows: 15 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `AnomalyCLIP`
  - stream/epsilon: `iid`, `0.0`
  - `toothbrush` emitted the expected feasible-ratio warning due sample-count constraints
  - `paper_allowed=false`
- MVTec full-category RareCLIP smoke sweep 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_sweep_rareclip.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_sweep_rareclip/metrics_mvtec_full_category_sweep_rareclip.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_sweep_rareclip/crd_lite_mvtec_full_category_sweep_rareclip.csv`
  - manifest: `results/latest/mvtec_full_category_sweep_rareclip/manifest_mvtec_full_category_sweep_rareclip.json`
  - rows: 15 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `RareCLIP`
  - stream/epsilon: `iid`, `0.0`
  - `toothbrush` emitted the expected feasible-ratio warning due sample-count constraints
  - `paper_allowed=false`
- MVTec full-category WinCLIP stream/epsilon matrix 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_stream_matrix_winclip.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_stream_matrix_winclip/metrics_mvtec_full_category_stream_matrix_winclip.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_stream_matrix_winclip/crd_lite_mvtec_full_category_stream_matrix_winclip.csv`
  - manifest: `results/latest/mvtec_full_category_stream_matrix_winclip/manifest_mvtec_full_category_stream_matrix_winclip.json`
  - rows: 90 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `WinCLIP`
  - stream/epsilon: `iid`, `bursty` × `0.0`, `0.01`, `0.05`
  - feasible-ratio warnings are expected where category sample counts cannot satisfy exact requested ratios without duplicates
  - `paper_allowed=false`
- MVTec full-category PatchCore stream/epsilon matrix 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_stream_matrix_patchcore.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_stream_matrix_patchcore/metrics_mvtec_full_category_stream_matrix_patchcore.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_stream_matrix_patchcore/crd_lite_mvtec_full_category_stream_matrix_patchcore.csv`
  - manifest: `results/latest/mvtec_full_category_stream_matrix_patchcore/manifest_mvtec_full_category_stream_matrix_patchcore.json`
  - rows: 90 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `PatchCore`
  - stream/epsilon: `iid`, `bursty` × `0.0`, `0.01`, `0.05`
  - feasible-ratio warnings are expected where category sample counts cannot satisfy exact requested ratios without duplicates
  - fitted-model cache was used under `results/latest/patchcore_model_cache/**` and remains ignored
  - `paper_allowed=false`
- MVTec full-category AnomalyCLIP stream/epsilon matrix 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_stream_matrix_anomalyclip.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_stream_matrix_anomalyclip/metrics_mvtec_full_category_stream_matrix_anomalyclip.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_stream_matrix_anomalyclip/crd_lite_mvtec_full_category_stream_matrix_anomalyclip.csv`
  - manifest: `results/latest/mvtec_full_category_stream_matrix_anomalyclip/manifest_mvtec_full_category_stream_matrix_anomalyclip.json`
  - rows: 90 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `AnomalyCLIP`
  - stream/epsilon: `iid`, `bursty` × `0.0`, `0.01`, `0.05`
  - feasible-ratio warnings are expected where category sample counts cannot satisfy exact requested ratios without duplicates
  - `paper_allowed=false`
- MVTec full-category RareCLIP stream/epsilon matrix 실행 완료:
  - command: `bash scripts/run_mvtec_full_category_stream_matrix_rareclip.sh`
  - aggregate metrics: `results/latest/mvtec_full_category_stream_matrix_rareclip/metrics_mvtec_full_category_stream_matrix_rareclip.csv`
  - CRD-lite summary: `results/latest/mvtec_full_category_stream_matrix_rareclip/crd_lite_mvtec_full_category_stream_matrix_rareclip.csv`
  - manifest: `results/latest/mvtec_full_category_stream_matrix_rareclip/manifest_mvtec_full_category_stream_matrix_rareclip.json`
  - rows: 90 measured_smoke rows
  - categories: all MVTec AD categories (`bottle,cable,capsule,carpet,grid,hazelnut,leather,metal_nut,pill,screw,tile,toothbrush,transistor,wood,zipper`)
  - baseline: `RareCLIP`
  - stream/epsilon: `iid`, `bursty` × `0.0`, `0.01`, `0.05`
  - feasible-ratio warnings are expected where category sample counts cannot satisfy exact requested ratios without duplicates
  - CPU fallback warnings are expected in this environment and do not indicate fake results
  - `paper_allowed=false`
- VisA WinCLIP iid smoke 실행 완료:
  - config: `experiments/configs/smoke_visa_winclip.yaml`
  - command: `bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip.yaml`
  - stream: `results/latest/stream_smoke_visa_winclip.json`
  - scores: `results/latest/scores_visa_winclip.csv`
  - metrics: `results/latest/metrics_visa_winclip.csv`
  - latest run: `results/latest/latest_run_visa_winclip.json`
  - manifest: `results/latest/manifest_visa_winclip.json`
  - result: 20 measured rows, labels `[0, 1]`, unique paths `20/20`, `status=measured_smoke`, `paper_allowed=false`
- VisA WinCLIP mini-matrix 6 runs 실행 완료:
  - config: `experiments/configs/visa_winclip_mini_matrix.yaml`
  - command: `bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_winclip_mini_matrix.yaml`
  - aggregate metrics: `results/latest/visa_mini_matrix/metrics_winclip_candle.csv`
  - CRD-lite summary: `results/latest/visa_mini_matrix/crd_lite_winclip_candle.csv`
  - aggregate manifest: `results/latest/visa_mini_matrix/manifest_winclip_candle.json`
  - rows: 6 measured_smoke rows
  - stream types: `iid`, `bursty`
  - epsilon: `0.0`, `0.01`, `0.05`
  - all generated streams have unique paths `20/20`; bursty streams record contiguous anomaly block metadata
  - ε=`0.01` emitted the expected feasible-ratio warning in iid and bursty runs
  - `paper_allowed=false`
- VisA WinCLIP bursty standalone smoke 실행 완료:
  - config: `experiments/configs/smoke_visa_winclip_bursty.yaml`
  - command: `bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip_bursty.yaml`
  - eval command: `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_winclip_bursty.csv --latest-run results/latest/latest_run_visa_winclip_bursty.json --output results/latest/metrics_visa_winclip_bursty.csv --manifest results/latest/manifest_visa_winclip_bursty.json`
  - stream: `results/latest/stream_smoke_visa_winclip_bursty.json`
  - scores: `results/latest/scores_visa_winclip_bursty.csv`
  - metrics: `results/latest/metrics_visa_winclip_bursty.csv`
  - latest run: `results/latest/latest_run_visa_winclip_bursty.json`
  - manifest: `results/latest/manifest_visa_winclip_bursty.json`
  - result: 20 measured rows, labels `[0, 1]`, unique paths `20/20`, contiguous anomaly block lengths `[1]`, `paper_allowed=false`
- VisA AnomalyCLIP iid standalone smoke 실행 완료:
  - config: `experiments/configs/smoke_visa_anomalyclip.yaml`
  - command: `bash scripts/run_smoke.sh experiments/configs/smoke_visa_anomalyclip.yaml`
  - eval command: `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_anomalyclip.csv --latest-run results/latest/latest_run_visa_anomalyclip.json --output results/latest/metrics_visa_anomalyclip.csv --manifest results/latest/manifest_visa_anomalyclip.json`
  - stream: `results/latest/stream_smoke_visa_anomalyclip.json`
  - scores: `results/latest/scores_visa_anomalyclip.csv`
  - metrics: `results/latest/metrics_visa_anomalyclip.csv`
  - latest run: `results/latest/latest_run_visa_anomalyclip.json`
  - manifest: `results/latest/manifest_visa_anomalyclip.json`
  - result: 20 measured rows, labels `[0, 1]`, unique paths `20/20`, `paper_allowed=false`
- VisA RareCLIP iid standalone smoke 실행 완료:
  - config: `experiments/configs/smoke_visa_rareclip.yaml`
  - command: `bash scripts/run_smoke.sh experiments/configs/smoke_visa_rareclip.yaml`
  - eval command: `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_rareclip.csv --latest-run results/latest/latest_run_visa_rareclip.json --output results/latest/metrics_visa_rareclip.csv --manifest results/latest/manifest_visa_rareclip.json`
  - stream: `results/latest/stream_smoke_visa_rareclip.json`
  - scores: `results/latest/scores_visa_rareclip.csv`
  - metrics: `results/latest/metrics_visa_rareclip.csv`
  - latest run: `results/latest/latest_run_visa_rareclip.json`
  - manifest: `results/latest/manifest_visa_rareclip.json`
  - result: 20 measured rows, labels `[0, 1]`, unique paths `20/20`, `paper_allowed=false`
- VisA PatchCore iid standalone smoke 실행 완료:
  - config: `experiments/configs/smoke_visa_patchcore.yaml`
  - command: `bash scripts/run_smoke.sh experiments/configs/smoke_visa_patchcore.yaml`
  - eval command: `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_patchcore.csv --latest-run results/latest/latest_run_visa_patchcore.json --output results/latest/metrics_visa_patchcore.csv --manifest results/latest/manifest_visa_patchcore.json`
  - stream: `results/latest/stream_smoke_visa_patchcore.json`
  - scores: `results/latest/scores_visa_patchcore.csv`
  - metrics: `results/latest/metrics_visa_patchcore.csv`
  - latest run: `results/latest/latest_run_visa_patchcore.json`
  - manifest: `results/latest/manifest_visa_patchcore.json`
  - result: 20 measured rows, labels `[0, 1]`, unique paths `20/20`, `status=measured_smoke`, `paper_allowed=false`
  - config uses `sampler: random` for repeatable smoke speed; the default approximate greedy coreset path also reached the same valid wrapper path but took about 23 minutes on CPU for VisA candle
- VisA full-category WinCLIP smoke sweep 실행 완료:
  - config: `experiments/configs/visa_full_category_sweep_winclip.yaml`
  - command: `bash scripts/run_visa_full_category_sweep_winclip.sh`
  - aggregate metrics: `results/latest/visa_full_category_sweep_winclip/metrics_visa_full_category_sweep_winclip.csv`
  - CRD-lite summary: `results/latest/visa_full_category_sweep_winclip/crd_lite_visa_full_category_sweep_winclip.csv`
  - aggregate manifest: `results/latest/visa_full_category_sweep_winclip/manifest_visa_full_category_sweep_winclip.json`
  - rows: 12 measured_smoke rows
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - baseline: `WinCLIP`
  - stream/epsilon: `iid`, `0.0`
  - all generated streams have unique paths `20/20`, labels `[0, 1]`, warnings `0`
  - `paper_allowed=false`
- VisA full-category AnomalyCLIP smoke sweep 실행 완료:
  - config: `experiments/configs/visa_full_category_sweep_anomalyclip.yaml`
  - command: `bash scripts/run_visa_full_category_sweep_anomalyclip.sh`
  - aggregate metrics: `results/latest/visa_full_category_sweep_anomalyclip/metrics_visa_full_category_sweep_anomalyclip.csv`
  - CRD-lite summary: `results/latest/visa_full_category_sweep_anomalyclip/crd_lite_visa_full_category_sweep_anomalyclip.csv`
  - aggregate manifest: `results/latest/visa_full_category_sweep_anomalyclip/manifest_visa_full_category_sweep_anomalyclip.json`
  - rows: 12 measured_smoke rows
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - baseline: `AnomalyCLIP`
  - stream/epsilon: `iid`, `0.0`
  - all generated streams have unique paths `20/20`, labels `[0, 1]`, warnings `0`
  - `paper_allowed=false`
- VisA full-category RareCLIP smoke sweep 실행 완료:
  - config: `experiments/configs/visa_full_category_sweep_rareclip.yaml`
  - command: `bash scripts/run_visa_full_category_sweep_rareclip.sh`
  - aggregate metrics: `results/latest/visa_full_category_sweep_rareclip/metrics_visa_full_category_sweep_rareclip.csv`
  - CRD-lite summary: `results/latest/visa_full_category_sweep_rareclip/crd_lite_visa_full_category_sweep_rareclip.csv`
  - aggregate manifest: `results/latest/visa_full_category_sweep_rareclip/manifest_visa_full_category_sweep_rareclip.json`
  - rows: 12 measured_smoke rows
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - baseline: `RareCLIP`
  - stream/epsilon: `iid`, `0.0`
  - all generated streams have unique paths `20/20`, labels `[0, 1]`, warnings `0`
  - CPU fallback warnings are expected in this environment and do not indicate fake results
  - `paper_allowed=false`
- VisA full-category WinCLIP stream/epsilon matrix 실행 완료:
  - config: `experiments/configs/visa_full_category_stream_matrix_winclip.yaml`
  - command: `bash scripts/run_visa_full_category_stream_matrix_winclip.sh`
  - aggregate metrics: `results/latest/visa_full_category_stream_matrix_winclip/metrics_visa_full_category_stream_matrix_winclip.csv`
  - CRD-lite summary: `results/latest/visa_full_category_stream_matrix_winclip/crd_lite_visa_full_category_stream_matrix_winclip.csv`
  - aggregate manifest: `results/latest/visa_full_category_stream_matrix_winclip/manifest_visa_full_category_stream_matrix_winclip.json`
  - rows: 72 measured_smoke rows
  - categories: all 12 local VisA categories
  - baseline: `WinCLIP`
  - stream/epsilon: `iid`, `bursty` × ε=`0.0`, `0.01`, `0.05`
  - generated streams: 72/72 length 20, unique paths `20/20`, labels `[0, 1]`
  - warnings: 24 expected `target_fraction_adjusted` warnings for ε=`0.01` because length 20 cannot exactly realize target fraction without duplicates
  - bursty metadata: 36 bursty streams, `applied_burst_lengths` present, observed lengths `[1, 2]`
  - `paper_allowed=false`
- VisA full-category AnomalyCLIP stream/epsilon matrix 실행 완료:
  - config: `experiments/configs/visa_full_category_stream_matrix_anomalyclip.yaml`
  - command: `bash scripts/run_visa_full_category_stream_matrix_anomalyclip.sh`
  - aggregate metrics: `results/latest/visa_full_category_stream_matrix_anomalyclip/metrics_visa_full_category_stream_matrix_anomalyclip.csv`
  - CRD-lite summary: `results/latest/visa_full_category_stream_matrix_anomalyclip/crd_lite_visa_full_category_stream_matrix_anomalyclip.csv`
  - aggregate manifest: `results/latest/visa_full_category_stream_matrix_anomalyclip/manifest_visa_full_category_stream_matrix_anomalyclip.json`
  - rows: 72 measured_smoke rows
  - categories: all 12 local VisA categories
  - baseline: `AnomalyCLIP`
  - stream/epsilon: `iid`, `bursty` × ε=`0.0`, `0.01`, `0.05`
  - generated streams: 72/72 length 20, unique paths `20/20`, labels `[0, 1]`
  - warnings: 24 expected `target_fraction_adjusted` warnings for ε=`0.01`
  - bursty metadata: 36 bursty streams, `applied_burst_lengths` present, observed lengths `[1, 2]`
  - `paper_allowed=false`
- VisA full-category RareCLIP stream/epsilon matrix 실행 완료:
  - config: `experiments/configs/visa_full_category_stream_matrix_rareclip.yaml`
  - command: `bash scripts/run_visa_full_category_stream_matrix_rareclip.sh`
  - aggregate metrics: `results/latest/visa_full_category_stream_matrix_rareclip/metrics_visa_full_category_stream_matrix_rareclip.csv`
  - CRD-lite summary: `results/latest/visa_full_category_stream_matrix_rareclip/crd_lite_visa_full_category_stream_matrix_rareclip.csv`
  - aggregate manifest: `results/latest/visa_full_category_stream_matrix_rareclip/manifest_visa_full_category_stream_matrix_rareclip.json`
  - rows: 72 measured_smoke rows
  - categories: all 12 local VisA categories
  - baseline: `RareCLIP`
  - stream/epsilon: `iid`, `bursty` × ε=`0.0`, `0.01`, `0.05`
  - generated streams: 72/72 length 20, unique paths `20/20`, labels `[0, 1]`
  - warnings: 24 expected `target_fraction_adjusted` warnings for ε=`0.01`
  - bursty metadata: 36 bursty streams, `applied_burst_lengths` present, observed lengths `[1, 2]`
  - CPU fallback warnings are expected in this environment and do not indicate fake results
  - `paper_allowed=false`

## 2. 검증 증거

최근 검증 명령:

```bash
bash scripts/run_smoke.sh experiments/configs/smoke_bursty.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_bursty.csv \
  --latest-run results/latest/latest_run_bursty.json \
  --output results/latest/metrics_bursty.csv \
  --manifest results/latest/manifest_bursty.json
bash scripts/run_patchcore_mini_matrix.sh
bash scripts/run_smoke.sh experiments/configs/smoke_winclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_winclip.csv \
  --latest-run results/latest/latest_run_winclip.json \
  --output results/latest/metrics_winclip.csv \
  --manifest results/latest/manifest_winclip.json
bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml
python3 experiments/mini_matrix.py aggregate experiments/configs/patchcore_mini_matrix.yaml
python3 experiments/mini_matrix.py aggregate experiments/configs/winclip_mini_matrix.yaml
bash scripts/run_category_quick_sweep.sh experiments/configs/category_quick_sweep.yaml
bash scripts/render_paper_tables.sh
bash scripts/build_paper.sh
bash scripts/run_mvtec_full_category_sweep.sh
bash scripts/run_mvtec_full_category_sweep_patchcore.sh
bash scripts/run_smoke.sh experiments/configs/smoke_anomalyclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_anomalyclip.csv \
  --latest-run results/latest/latest_run_anomalyclip.json \
  --output results/latest/metrics_anomalyclip.csv \
  --manifest results/latest/manifest_anomalyclip.json
bash scripts/run_smoke.sh experiments/configs/smoke_rareclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_rareclip.csv \
  --latest-run results/latest/latest_run_rareclip.json \
  --output results/latest/metrics_rareclip.csv \
  --manifest results/latest/manifest_rareclip.json
bash scripts/run_baseline_mini_matrix.sh experiments/configs/anomalyclip_mini_matrix.yaml
bash scripts/run_baseline_mini_matrix.sh experiments/configs/rareclip_mini_matrix.yaml
bash scripts/run_mvtec_full_category_sweep_anomalyclip.sh
bash scripts/run_mvtec_full_category_sweep_rareclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_winclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_anomalyclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_rareclip.sh
bash scripts/run_mvtec_full_category_stream_matrix_patchcore.sh
python3 experiments/make_streams.py --config experiments/configs/smoke_visa_winclip.yaml
bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_winclip.csv \
  --latest-run results/latest/latest_run_visa_winclip.json \
  --output results/latest/metrics_visa_winclip.csv \
  --manifest results/latest/manifest_visa_winclip.json
bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_winclip_mini_matrix.yaml
bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip_bursty.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_winclip_bursty.csv \
  --latest-run results/latest/latest_run_visa_winclip_bursty.json \
  --output results/latest/metrics_visa_winclip_bursty.csv \
  --manifest results/latest/manifest_visa_winclip_bursty.json
bash scripts/run_smoke.sh experiments/configs/smoke_visa_anomalyclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_anomalyclip.csv \
  --latest-run results/latest/latest_run_visa_anomalyclip.json \
  --output results/latest/metrics_visa_anomalyclip.csv \
  --manifest results/latest/manifest_visa_anomalyclip.json
bash scripts/run_smoke.sh experiments/configs/smoke_visa_rareclip.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_rareclip.csv \
  --latest-run results/latest/latest_run_visa_rareclip.json \
  --output results/latest/metrics_visa_rareclip.csv \
  --manifest results/latest/manifest_visa_rareclip.json
bash scripts/run_smoke.sh experiments/configs/smoke_visa_patchcore.yaml
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores_visa_patchcore.csv \
  --latest-run results/latest/latest_run_visa_patchcore.json \
  --output results/latest/metrics_visa_patchcore.csv \
  --manifest results/latest/manifest_visa_patchcore.json
bash scripts/run_visa_full_category_sweep_winclip.sh
bash scripts/run_visa_full_category_sweep_anomalyclip.sh
bash scripts/run_visa_full_category_sweep_rareclip.sh
bash scripts/run_visa_full_category_stream_matrix_winclip.sh
bash scripts/run_visa_full_category_stream_matrix_anomalyclip.sh
bash scripts/run_visa_full_category_stream_matrix_rareclip.sh
python3 -m unittest discover -v
python3 -m compileall experiments tests
git diff --check
```

검증 결과:

- unittest: 41 tests OK
- compileall: OK
- diff check: OK
- paper build: OK, local environment has no `pdflatex`, so dependency-free placeholder PDF fallback was written
- mini-matrix aggregate: 6 rows, all `measured_smoke`, `paper_allowed=false`
- WinCLIP smoke: 20 measured rows, evaluated smoke manifest `paper_allowed=false`
- WinCLIP mini-matrix aggregate: 6 rows, all `measured_smoke`, `paper_allowed=false`
- CRD-lite summaries: PatchCore/WinCLIP 각 6 rows, all `derived_smoke`, `paper_allowed=false`
- Category quick sweep: 6 rows, categories `bottle/capsule/hazelnut`, baselines `PatchCore/WinCLIP`, all `measured_smoke`, `paper_allowed=false`
- MVTec full-category WinCLIP sweep: 15 rows, all MVTec AD categories, all `measured_smoke`, `paper_allowed=false`
- MVTec full-category PatchCore sweep: 15 rows, all MVTec AD categories, all `measured_smoke`, `paper_allowed=false`
- AnomalyCLIP smoke: 20 measured rows, evaluated smoke manifest `paper_allowed=false`
- RareCLIP smoke: 20 measured rows, evaluated smoke manifest `paper_allowed=false`
- AnomalyCLIP mini-matrix aggregate: 6 rows, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- RareCLIP mini-matrix aggregate: 6 rows, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- MVTec full-category AnomalyCLIP sweep: 15 rows, all MVTec AD categories, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- MVTec full-category RareCLIP sweep: 15 rows, all MVTec AD categories, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- MVTec full-category WinCLIP stream/epsilon matrix: 90 rows, all MVTec AD categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- MVTec full-category AnomalyCLIP stream/epsilon matrix: 90 rows, all MVTec AD categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- MVTec full-category RareCLIP stream/epsilon matrix: 90 rows, all MVTec AD categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- MVTec full-category PatchCore stream/epsilon matrix: 90 rows, all MVTec AD categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- VisA WinCLIP iid smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA WinCLIP mini-matrix: 6 rows, dataset `VisA`, category `candle`, stream types `iid/bursty`, epsilon `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, aggregate manifest `paper_allowed=false`
- VisA WinCLIP bursty standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, contiguous anomaly block lengths `[1]`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA AnomalyCLIP iid standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA RareCLIP iid standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA PatchCore iid standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA full-category WinCLIP sweep: 12 rows, all 12 local VisA categories, all `measured_smoke`, all generated streams unique paths `20/20`, labels `[0, 1]`, aggregate manifest `paper_allowed=false`
- VisA full-category AnomalyCLIP sweep: 12 rows, all 12 local VisA categories, all `measured_smoke`, all generated streams unique paths `20/20`, labels `[0, 1]`, aggregate manifest `paper_allowed=false`
- VisA full-category RareCLIP sweep: 12 rows, all 12 local VisA categories, all `measured_smoke`, all generated streams unique paths `20/20`, labels `[0, 1]`, aggregate manifest `paper_allowed=false`
- VisA full-category WinCLIP stream/epsilon matrix: 72 rows, all 12 local VisA categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, warning count 24, aggregate manifest `paper_allowed=false`
- VisA full-category AnomalyCLIP stream/epsilon matrix: 72 rows, all 12 local VisA categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, warning count 24, aggregate manifest `paper_allowed=false`
- VisA full-category RareCLIP stream/epsilon matrix: 72 rows, all 12 local VisA categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, warning count 24, aggregate manifest `paper_allowed=false`

## 3. 지금 논문 관점에서 어디까지 왔나

현재는 **MVTec AD 기준 4개 baseline(PatchCore/WinCLIP/AnomalyCLIP/RareCLIP)의 all-category stream/epsilon smoke matrix가 동작하고, VisA는 CLIP 3개 baseline(WinCLIP/AnomalyCLIP/RareCLIP)의 all-12-category stream/epsilon smoke matrix가 동작함을 입증한 단계**다.

구체적으로:

1. stream protocol은 구현되어 재현 가능하다.
2. iid/bursty 둘 다 실제 PatchCore scoring까지 통과했다.
3. epsilon sweep의 no-duplicate/closest-ratio/warning 정책이 실제 metadata로 남는다.
4. baseline-parametric mini-matrix runner가 동작한다.
5. PatchCore/WinCLIP/AnomalyCLIP/RareCLIP 모두 bottle에서 `iid/bursty × ε 0/0.01/0.05` aggregate metric CSV와 CRD-lite smoke summary까지 생성된다.
6. PatchCore와 WinCLIP은 bottle/capsule/hazelnut iid ε=0 quick sweep까지 통과했다.
7. PatchCore와 WinCLIP은 all-15-category `iid/bursty × ε 0/0.01/0.05` stream matrix까지 통과했다.
8. AnomalyCLIP은 MVTec AD bottle mini-matrix와 all-15-category `iid/bursty × ε 0/0.01/0.05` stream matrix까지 실제 image-level score를 생성했다.
9. RareCLIP은 MVTec AD bottle mini-matrix와 all-15-category `iid/bursty × ε 0/0.01/0.05` stream matrix까지 실제 online image-level score를 생성했다.
10. VisA adapter는 `candle` 기준 `iid/bursty × ε 0/0.01/0.05` length=20 streams를 만들고 WinCLIP으로 실제 image-level score를 생성했다.
11. VisA candle iid ε=0 length=20은 AnomalyCLIP과 RareCLIP에서도 실제 image-level score를 생성했다.
12. VisA all-12-category iid ε=0 length=20은 WinCLIP, AnomalyCLIP, RareCLIP으로 실제 image-level score를 생성했다.
13. VisA all-12-category `iid/bursty × ε 0/0.01/0.05` length=20은 WinCLIP, AnomalyCLIP, RareCLIP으로 실제 image-level score를 생성했다.
14. VisA candle iid ε=0 length=20은 PatchCore에서도 실제 image-level score를 생성했다.

하지만 아직 **논문 결과 단계는 아니다**.

부족한 것:

- CLIP baseline은 MVTec/VisA 모두 WinCLIP/AnomalyCLIP/RareCLIP full all-category stream/epsilon smoke matrix까지 완료
- MVTec 전체 category는 PatchCore/WinCLIP/AnomalyCLIP/RareCLIP 모두 `iid/bursty × ε 0/0.01/0.05` smoke matrix 완료
- VisA는 WinCLIP/AnomalyCLIP/RareCLIP all-category stream/epsilon matrix까지 실행됨; PatchCore VisA는 candle iid ε=0 smoke만 완료
- full P0 matrix 미실행
- CRD-lite는 smoke aggregate summary로 구현됨; full P0/VisA 검증과 paper 해석은 미완
- paper table pipeline은 smoke evidence table만 생성함; full matrix 기반 table/figure는 아직 아님
- review 전이므로 `paper_allowed=true` 금지

## 4. 다음 에이전트가 빠르게 해야 할 일

### 1순위 — VisA coverage 확장

VisA stream adapter와 CLIP baselines(WinCLIP/AnomalyCLIP/RareCLIP) all-category stream/epsilon smoke matrix는 연결됐고, PatchCore도 candle iid ε=0 smoke가 통과했다. 다음은 PatchCore VisA candle mini-matrix 또는 all-category iid ε=0 sweep로 확장한다.

### 2순위 — full P0 orchestration 설계

VisA 연결 후에는 P0 config를 실제 실행 단위로 쪼개고 memory policy/calibration 차원을 paper gate 전용 검증 루프로 올린다.

## 5. 주의할 점

- `bursty` 성공 기준은 “하나 이상의 contiguous anomaly block”이다. 현재 bottle/prevalence 0.05는 anomaly 1개라 block `[1]`이 정상이다.
- `epsilon=0.01`은 bottle의 sample count 제약 때문에 exact 0.06을 못 맞춰 warning이 기록된다. 이것은 의도된 정책이다.
- PatchCore latency는 true online latency가 아니라 `offline_batch_amortized`다. 논문에서 온라인 latency처럼 쓰면 안 된다.
- WinCLIP smoke latency는 wrapper batch inference amortized latency다. full benchmark 전에는 pipeline evidence로만 해석한다.
- AnomalyCLIP smoke latency는 CPU single-image wrapper latency이며 ViT-L/14@336px라 느리다. 온라인 latency 결론으로 쓰지 않는다.
- RareCLIP smoke latency는 CPU single-image online-memory wrapper latency이며 ViT-L/14@336px라 느리다. online update 경로 검증용이지 최종 latency 결론으로 쓰지 않는다.
- 현재 ECE는 baseline anomaly score min-max 기반 diagnostic이다. calibrated probability로 해석 금지.
- 현재 CRD-lite는 bottle mini-matrix aggregate에서 파생한 signed smoke diagnostic이다. full P0 결과처럼 해석 금지.
- Category quick sweep은 iid ε=0 length=20 smoke이다. category 확장성 확인용이며 full-category/full-epsilon benchmark가 아니다.
- MVTec full-category PatchCore/WinCLIP/AnomalyCLIP/RareCLIP stream matrices는 iid/bursty × ε smoke coverage이다. full P0, VisA, or paper-reviewed benchmark가 아니다.
- VisA CLIP all-category stream/epsilon matrices와 candle smoke들은 adapter/scoring path 검증용이다. VisA 전체 P0 결과나 논문 결론으로 해석 금지.
- `render_paper_tables.py`는 결과를 “논문 결론”으로 승격하지 않는다. 현재 생성 표는 smoke evidence table이며 `paper_allowed=false`를 명시한다.
