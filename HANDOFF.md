# HANDOFF — ZIAD 논문 구현 현재 상태

최종 갱신: 2026-05-20
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
- PatchCore mini-matrix runner 구현 완료: `scripts/run_patchcore_mini_matrix.sh`
  - `iid/bursty × epsilon 0/0.01/0.05`, MVTec AD bottle, PatchCore only

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
  - aggregate manifest: `results/latest/mini_matrix/manifest_patchcore_bottle.json`
  - rows: 6 measured_smoke rows
  - stream types: `iid`, `bursty`
  - epsilon: `0.0`, `0.01`, `0.05`
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
python3 -m unittest discover -v
python3 -m compileall experiments tests
git diff --check
```

검증 결과:

- unittest: 21 tests OK
- compileall: OK
- diff check: OK
- mini-matrix aggregate: 6 rows, all `measured_smoke`, `paper_allowed=false`

## 3. 지금 논문 관점에서 어디까지 왔나

현재는 **실험 파이프라인의 PatchCore-only paper-run plumbing이 동작함을 입증한 단계**다.

구체적으로:

1. stream protocol은 구현되어 재현 가능하다.
2. iid/bursty 둘 다 실제 PatchCore scoring까지 통과했다.
3. epsilon sweep의 no-duplicate/closest-ratio/warning 정책이 실제 metadata로 남는다.
4. aggregate metric CSV까지 생성된다.

하지만 아직 **논문 결과 단계는 아니다**.

부족한 것:

- CLIP baseline 실제 wrapper가 없음: WinCLIP/RareCLIP/AnomalyCLIP 미완
- MVTec 전체 category 미실행
- VisA 미실행
- full P0 matrix 미실행
- CRD-lite 구현 미완
- paper table/figure가 full matrix 기반이 아님
- review 전이므로 `paper_allowed=true` 금지

## 4. 다음 에이전트가 빠르게 해야 할 일

### 1순위 — WinCLIP wrapper 구현

논문 주제가 CLIP ZSAD이므로 PatchCore만으로는 부족하다. 다음은 **WinCLIP**을 먼저 붙이는 것이 가장 빠른 CLIP baseline 경로다.

시작 파일:

- `experiments/baselines/winclip.py`
- `external/WinClip`
- `experiments/configs/baselines.yaml`
- `scripts/run_smoke.sh`

성공 기준:

```bash
# WinCLIP용 smoke config를 만든 뒤
bash scripts/run_smoke.sh experiments/configs/smoke_winclip.yaml
python3 experiments/evaluate.py \
  --scores-csv <winclip_scores.csv> \
  --latest-run <winclip_latest_run.json> \
  --output <winclip_metrics.csv> \
  --manifest <winclip_manifest.json>
```

출력은 반드시 common score schema:

```csv
stream_index,image_path,label,category,anomaly_score,latency_ms,peak_vram_mb,status
```

### 2순위 — mini-matrix runner를 baseline-parametric으로 일반화

현재 `scripts/run_patchcore_mini_matrix.sh`는 PatchCore 고정이다. WinCLIP이 붙으면 baseline 이름/path를 config에서 받아 같은 matrix를 돌리게 일반화한다.

목표:

```bash
bash scripts/run_baseline_mini_matrix.sh experiments/configs/winclip_mini_matrix.yaml
```

### 3순위 — MVTec category sweep

MVTec bottle만 통과했으므로 전체 category sweep으로 확장한다.

권장 순서:

1. bottle 유지로 WinCLIP smoke 성공
2. MVTec 2~3개 category quick sweep
3. MVTec full category sweep

### 4순위 — CRD-lite와 paper table pipeline

epsilon 0/0.01/0.05 결과가 생겼으므로 CRD-lite를 aggregate metrics에서 계산할 수 있게 한다.

필요 작업:

- epsilon별 AUROC/AUPR drop 계산
- `results/latest/tables/*.tex`를 mini/full matrix 기반으로 생성
- paper text는 아직 TODO 유지

### 5순위 — VisA 연결

VisA는 dataset/helper 성격상 `external/spot-diff`와 `data/visa/` 구조를 확인한 뒤 MVTec stream item schema와 동일하게 맞춘다.

## 5. 주의할 점

- `bursty` 성공 기준은 “하나 이상의 contiguous anomaly block”이다. 현재 bottle/prevalence 0.05는 anomaly 1개라 block `[1]`이 정상이다.
- `epsilon=0.01`은 bottle의 sample count 제약 때문에 exact 0.06을 못 맞춰 warning이 기록된다. 이것은 의도된 정책이다.
- PatchCore latency는 true online latency가 아니라 `offline_batch_amortized`다. 논문에서 온라인 latency처럼 쓰면 안 된다.
- 현재 ECE는 PatchCore score min-max 기반 diagnostic이다. calibrated probability로 해석 금지.
