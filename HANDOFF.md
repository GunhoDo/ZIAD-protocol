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
- deterministic MVTec stream generator 구현 완료: `experiments/make_streams.py`
  - fields: `stream_index,image_path,label,category,source_split,anomaly_type`
  - no duplicate samples
  - label integrity 유지
  - requested prevalence/epsilon을 정확히 못 맞추면 가장 가까운 feasible ratio 선택
  - 실제 applied stats와 warnings를 stream metadata에 기록
  - `iid`, `bursty` 지원
  - `bursty`는 anomaly가 contiguous block(s)에 들어가도록 보장
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
bash scripts/run_baseline_mini_matrix.sh experiments/configs/anomalyclip_mini_matrix.yaml
bash scripts/run_mvtec_full_category_sweep_anomalyclip.sh
python3 -m unittest discover -v
python3 -m compileall experiments tests
git diff --check
```

검증 결과:

- unittest: 34 tests OK
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
- AnomalyCLIP mini-matrix aggregate: 6 rows, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`
- MVTec full-category AnomalyCLIP sweep: 15 rows, all MVTec AD categories, all `measured_smoke`, CRD-lite all `derived_smoke`, `paper_allowed=false`

## 3. 지금 논문 관점에서 어디까지 왔나

현재는 **실험 파이프라인의 PatchCore paper-run plumbing, WinCLIP mini-matrix/all-category smoke path, AnomalyCLIP mini-matrix/all-category smoke path가 동작함을 입증한 단계**다.

구체적으로:

1. stream protocol은 구현되어 재현 가능하다.
2. iid/bursty 둘 다 실제 PatchCore scoring까지 통과했다.
3. epsilon sweep의 no-duplicate/closest-ratio/warning 정책이 실제 metadata로 남는다.
4. baseline-parametric mini-matrix runner가 동작한다.
5. PatchCore와 WinCLIP 모두 bottle에서 `iid/bursty × ε 0/0.01/0.05` aggregate metric CSV와 CRD-lite smoke summary까지 생성된다.
6. PatchCore와 WinCLIP은 bottle/capsule/hazelnut iid ε=0 quick sweep까지 통과했다.
7. PatchCore와 WinCLIP 모두 all-15-category MVTec AD iid ε=0 smoke sweep까지 통과했다.
8. AnomalyCLIP은 MVTec AD bottle에서 `iid/bursty × ε 0/0.01/0.05` mini-matrix까지, 그리고 all-15-category iid ε=0 smoke까지 실제 image-level score를 생성했다.

하지만 아직 **논문 결과 단계는 아니다**.

부족한 것:

- CLIP baseline은 WinCLIP bottle mini-matrix/all-category iid ε=0 smoke와 AnomalyCLIP bottle mini-matrix/all-category iid ε=0 smoke까지 완료: RareCLIP 미완, WinCLIP/AnomalyCLIP full bursty/epsilon category matrix 미실행
- MVTec 전체 category는 PatchCore/WinCLIP iid ε=0 smoke만 완료; full epsilon/bursty matrix는 미완
- VisA 미실행
- full P0 matrix 미실행
- CRD-lite는 bottle mini-matrix smoke summary만 구현됨; full P0/category/VisA 검증 미완
- paper table pipeline은 smoke evidence table만 생성함; full matrix 기반 table/figure는 아직 아님
- review 전이므로 `paper_allowed=true` 금지

## 4. 다음 에이전트가 빠르게 해야 할 일

### 1순위 — RareCLIP wrapper 구현

남은 CLIP baseline을 같은 stream contract에 맞춘다. fake score 금지, upstream loader가 stream order를 무시하면 wrapper가 직접 stream JSON을 읽어야 한다.

### 2순위 — all-category epsilon/bursty 확장

PatchCore/WinCLIP/AnomalyCLIP 모두 all-category iid ε=0 smoke는 통과했다. 다음 확장은 full P0 전에 `bursty`와 ε=`0.01/0.05`를 카테고리 전체로 넓히는 것이다. 실행 시간과 산출물 크기가 커지므로 baseline별로 분리하고 aggregate row count, feasible-ratio warnings, `paper_allowed=false`를 검증한다.

### 3순위 — VisA 연결

VisA는 dataset/helper 성격상 `external/spot-diff`와 `data/visa/` 구조를 확인한 뒤 MVTec stream item schema와 동일하게 맞춘다.

## 5. 주의할 점

- `bursty` 성공 기준은 “하나 이상의 contiguous anomaly block”이다. 현재 bottle/prevalence 0.05는 anomaly 1개라 block `[1]`이 정상이다.
- `epsilon=0.01`은 bottle의 sample count 제약 때문에 exact 0.06을 못 맞춰 warning이 기록된다. 이것은 의도된 정책이다.
- PatchCore latency는 true online latency가 아니라 `offline_batch_amortized`다. 논문에서 온라인 latency처럼 쓰면 안 된다.
- WinCLIP smoke latency는 wrapper batch inference amortized latency다. full benchmark 전에는 pipeline evidence로만 해석한다.
- AnomalyCLIP smoke latency는 CPU single-image wrapper latency이며 ViT-L/14@336px라 느리다. 온라인 latency 결론으로 쓰지 않는다.
- 현재 ECE는 baseline anomaly score min-max 기반 diagnostic이다. calibrated probability로 해석 금지.
- 현재 CRD-lite는 bottle mini-matrix aggregate에서 파생한 signed smoke diagnostic이다. full P0 결과처럼 해석 금지.
- Category quick sweep은 iid ε=0 length=20 smoke이다. category 확장성 확인용이며 full-category/full-epsilon benchmark가 아니다.
- MVTec full-category PatchCore/WinCLIP/AnomalyCLIP sweeps도 iid ε=0 length=20 smoke이다. all-category path 검증용이며 bursty/epsilon/full-P0 benchmark가 아니다.
- `render_paper_tables.py`는 결과를 “논문 결론”으로 승격하지 않는다. 현재 생성 표는 smoke evidence table이며 `paper_allowed=false`를 명시한다.
