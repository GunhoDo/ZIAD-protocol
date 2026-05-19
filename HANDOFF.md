# HANDOFF — ZIAD Protocol PatchCore Smoke Evaluation

작성일: 2026-05-19  
프로젝트: `ZIAD-protocol`  
목표: CLIP/산업 이상탐지 baseline들을 streaming 조건에서 평가하는 실험 프로토콜 구축

---

## 1. 대화 흐름 요약

### 1.1 OMX setup 및 프로젝트 기준 확인

- 프로젝트는 `AGENTS.md`와 `docs/experiment-prd.md`를 canonical reference로 둔다.
- 중요한 규칙:
  - baseline URL/commit은 근거 없이 지어내지 않는다.
  - `results/latest/`에 fake metric을 넣지 않는다.
  - 실제 측정 전/검토 전에는 `paper_allowed: false`를 유지한다.
  - `data/**`, `external/**`은 로컬 자산이며 gitignore 대상이다.

### 1.2 `external/README.md` URL 검토

사용자는 `external/README.md`의 URL이 현재 PRD에서 의도한 baseline인지 확인해 달라고 했다.
접근 가능 여부가 아니라, “현재 clone되어 있는 repo가 우리 baseline 의도와 맞는지”를 확인하는 것이 목적이었다.

확인된 로컬 clone 상태:

| Baseline | Local path | Origin URL | HEAD |
|---|---|---|---|
| RareCLIP | `external/RareCLIP` | `https://github.com/hjf02/RareCLIP.git` | `a8e6d46ee2612a0edbf48c3b88e9998497e2b422` |
| PatchCore | `external/patchcore-inspection` | `https://github.com/amazon-science/patchcore-inspection.git` | `fcaa92f124fb1ad74a7acf56726decd4b27cbcad` |
| WinCLIP | `external/WinClip` | `https://github.com/caoyunkang/WinClip.git` | `a2ee822d77d01fb7beaed54314e61fe34d5027a4` |
| AnomalyCLIP | `external/AnomalyCLIP` | `https://github.com/zqhang/AnomalyCLIP.git` | `3911738c0867544f545a076ad78f3f11d9ecbfdf` |

중요한 수정/해석:

- 기존 예상 path `external/PatchCore`는 실제 clone 기준으로 `external/patchcore-inspection`이 맞다.
- 기존 예상 path `external/WinCLIP`는 실제 clone 기준으로 `external/WinClip`이 맞다.
- 사용자의 지시에 따라 “우리 예상이 틀린 경우 현재 clone 기준으로 바꾸는” 방향이 채택되었다.

### 1.3 `run_smoke.sh` provenance 코드 의도 설명

사용자가 아래 코드의 의도를 물었다.

```bash
mkdir -p results/latest

BASELINE_REPO_URL="TBD"
BASELINE_COMMIT_HASH="TBD"
if [ -d "${SMOKE_BASELINE_PATH}/.git" ]; then
  BASELINE_REPO_URL="$(git -C "${SMOKE_BASELINE_PATH}" remote get-url origin 2>/dev/null || echo TBD)"
  BASELINE_COMMIT_HASH="$(git -C "${SMOKE_BASELINE_PATH}" rev-parse HEAD 2>/dev/null || echo TBD)"
fi
```

설명한 의도:

- `results/latest` 산출물 디렉터리를 보장한다.
- baseline clone이 있으면 실제 origin URL과 commit hash를 provenance로 기록한다.
- clone이 없거나 git command가 실패하면 `TBD`로 남겨 fake provenance를 만들지 않는다.
- 즉, 실험 결과가 어느 baseline 코드 버전에서 나왔는지 추적하기 위한 안전장치다.

### 1.4 `spot-diff` repo 위치 설명

사용자가 `https://github.com/amazon-science/spot-diff`를 어디에 두어야 하는지 물었다.

설명한 결론:

- `spot-diff`는 baseline model repo가 아니라 VisA dataset/reorganization/helper 성격의 repo다.
- 따라서 최종 dataset 파일은 `data/visa/` 아래에 두는 것이 맞다.
- repo clone 자체가 필요하면 `data/`가 아니라 `external/spot-diff`에 두는 것이 맞다.
- 현재 로컬에는 `external/spot-diff`가 존재하고, `utils/prepare_data.py` 같은 helper가 있다.

### 1.5 데이터 준비 상태

사용자가 “data는 다 넣었다”고 했다.
확인/이후 작업 중 MVTec AD는 아래 상태로 사용되었다.

- `data/mvtec_ad/bottle` 존재
- `train/good`, `test/*`, `ground_truth/*` 구조 존재
- PatchCore smoke는 MVTec AD `bottle` category 기준으로 실행됨

---

## 2. PatchCore wrapper 구현 요약

사용자 요청:

```text
$ralph PatchCore의 실행 표면을 분석해줘 이후 wrapper를 구현해줘
```

구현 파일:

- `experiments/baselines/patchcore.py`

핵심 구현:

- upstream repo: `external/patchcore-inspection`
- upstream `src`를 `sys.path`에 추가해 다음 모듈을 사용:
  - `patchcore.backbones`
  - `patchcore.common`
  - `patchcore.patchcore`
  - `patchcore.sampler`
  - `patchcore.utils`
  - `patchcore.datasets.mvtec.MVTecDataset`
- MVTec train split으로 memory bank 생성
- MVTec test split에 대해 image-level anomaly score 산출
- 공통 score CSV schema에 맞춰 기록:

```csv
stream_index,image_path,label,category,anomaly_score,latency_ms,peak_vram_mb,status
```

기본 smoke 설정:

- category: `bottle`
- seed: `0`
- resize: `256`
- imagesize: `224`
- batch_size: `2`
- num_workers: `0`
- backbone: `wideresnet50`
- layers: `layer2,layer3`
- sampler: `approx_greedy_coreset`
- sampler_percentage: `0.1`
- target dimensions: `1024`
- anomaly_scorer_num_nn: `1`
- patchsize: `3`
- faiss_on_gpu: `false`
- faiss_num_workers: `8`

지원한 환경변수:

- `PATCHCORE_MAX_TEST_IMAGES`
- 기타 PatchCore config override용 `PATCHCORE_*`

관련 변경:

- `experiments/configs/baselines.yaml`
  - PatchCore path를 `external/patchcore-inspection` 기준으로 조정
  - setup command에 `timm` 추가
- `scripts/run_smoke.sh`
  - 성공 시 `latest_run.json`, `manifest.json`에 실제 provenance와 status 기록
  - `paper_allowed`는 계속 `false`

설치한 dependency:

```bash
python3 -m pip install -r external/patchcore-inspection/requirements.txt
python3 -m pip install timm
```

이유:

- upstream PatchCore가 `timm`을 import하지만 requirements에 빠져 있어 smoke 실행에 필요했다.

검증 결과:

```bash
bash scripts/run_smoke.sh
```

- 성공
- `results/latest/scores.csv`에 83 measured rows 생성
- status는 모두 `measured`
- label은 `0`, `1` 모두 존재
- `manifest.paper_allowed`는 `false` 유지

---

## 3. PatchCore smoke 결과 평가기 구현 요약

사용자 요청:

```text
$ralph PatchCore smoke 결과를 평가하는 evaluate.py를 구현해줘
```

구현 파일:

- `experiments/evaluate.py`
- `tests/test_evaluate.py`

### 3.1 `experiments/evaluate.py` 기능

기존 placeholder evaluator를 실제 score 기반 evaluator로 교체했다.

CLI:

```bash
python3 experiments/evaluate.py \
  --scores-csv results/latest/scores.csv \
  --latest-run results/latest/latest_run.json \
  --output results/latest/metrics.csv \
  --manifest results/latest/manifest.json
```

인자를 생략하면 위 경로들이 기본값이다.

측정 row 처리:

- `scores.csv` header가 wrapper contract와 일치하는지 검증한다.
- `status != placeholder_not_measured`인 row만 measured row로 본다.
- binary label `0/1`만 허용한다.
- 계산 metric:
  - `image_auroc`: `sklearn.metrics.roc_auc_score`
  - `aupr`: `sklearn.metrics.average_precision_score`
  - `ece`: PatchCore anomaly score를 min-max normalization한 뒤 10-bin binary ECE 계산
  - `latency_ms`: 평균 latency
  - `crd_lite`: 단일 smoke run만으로는 계산할 수 없어 `NA`

주의:

- PatchCore score는 calibrated probability가 아니다.
- 따라서 현재 ECE는 smoke tracking용 diagnostic 값이며 paper-ready calibration evidence가 아니다.

placeholder row 처리:

- `scores.csv`가 placeholder만 포함하면 기존처럼 `placeholder_not_measured` metric row를 유지한다.
- fake metric을 만들지 않는다.

출력 artifacts:

- `results/latest/metrics.csv`
- `results/latest/tables/baseline_summary.tex`
- `results/latest/figures/contamination_drop_placeholder.txt`
- `results/latest/manifest.json`

manifest safety:

- `status`: `evaluated_smoke`
- `paper_allowed`: `false`
- full P0 및 review 전에는 paper gate를 열지 않는다.

### 3.2 현재 metric 결과

현재 `results/latest/metrics.csv`:

```csv
dataset,stream_type,prevalence,contamination_epsilon,baseline,memory_policy,calibration,image_auroc,aupr,ece,latency_ms,crd_lite,status
MVTec AD,iid,0.05,0,PatchCore,default/SCS,none,1.000000,1.000000,0.349791,521.285063,NA,measured_smoke
```

해석:

- 이 값은 현재 smoke run 산출물에서 계산된 실제 값이다.
- 단, smoke-only이며 paper-ineligible이다.
- `paper_allowed`는 여전히 `false`다.

### 3.3 테스트 추가

추가 파일:

- `tests/__init__.py`
- `tests/test_patchcore_wrapper.py`
- `tests/test_evaluate.py`

`tests/test_evaluate.py` 커버리지:

- measured score rows에서 metric row 계산
- placeholder score rows는 placeholder metric 유지
- `evaluate(...)` 호출 시 metrics/manifest artifact write 확인

---

## 4. 검증 증거

마지막 확인 기준으로 통과한 명령:

```bash
python3 -m unittest discover -s tests
```

결과:

```text
Ran 6 tests in 0.356s
OK
```

추가 검증:

```bash
python3 -m py_compile \
  experiments/evaluate.py \
  tests/test_evaluate.py \
  experiments/baselines/patchcore.py \
  tests/test_patchcore_wrapper.py
```

- 통과

```bash
bash -n scripts/run_smoke.sh scripts/setup_baselines.sh
```

- 통과

```bash
python3 experiments/evaluate.py
```

출력:

```text
results/latest/metrics.csv
results/latest/manifest.json
status=measured_smoke
```

artifact assertion:

- `metrics.csv`에 PatchCore row 1개 존재
- `status == measured_smoke`
- `image_auroc`, `aupr`, `ece`가 TODO가 아님
- `crd_lite == NA`
- `manifest.status == evaluated_smoke`
- `manifest.paper_allowed is false`

score audit:

```text
score_rows 83
statuses ['measured']
labels ['0', '1']
```

---

## 5. 현재 주요 변경 파일

마지막 확인 시 `git status --short` 기준:

```text
 M experiments/baselines/patchcore.py
 M experiments/configs/baselines.yaml
 M experiments/evaluate.py
 M results/latest/figures/contamination_drop_placeholder.txt
 M results/latest/latest_run.json
 M results/latest/manifest.json
 M results/latest/metrics.csv
 M results/latest/scores.csv
 M results/latest/tables/baseline_summary.tex
 M scripts/run_smoke.sh
?? tests/
```

주의:

- `experiments/baselines/patchcore.py`, `baselines.yaml`, `scripts/run_smoke.sh`, `scores.csv`, `latest_run.json`은 PatchCore wrapper smoke 실행 작업에서 생긴 변경이다.
- `experiments/evaluate.py`, `tests/test_evaluate.py`, `metrics.csv`, `manifest.json`, table/figure artifact는 PatchCore smoke 평가기 작업에서 생긴 변경이다.
- 이전 변경을 되돌리지 말고, 필요한 경우 목적별 commit으로 나누는 것이 좋다.

---

## 6. 중요한 설계 결정

### 6.1 fake result 방지

- placeholder input이면 placeholder output을 유지한다.
- measured score가 있을 때만 metric을 계산한다.
- 단일 smoke run으로 계산할 수 없는 CRD-lite는 `NA`로 둔다.
- full P0 및 검토 전까지 `paper_allowed: false`를 유지한다.

### 6.2 PatchCore ECE는 diagnostic only

- PatchCore anomaly score는 확률이 아니다.
- 현재 ECE는 min-max normalized score 기반 smoke diagnostic이다.
- 논문용 calibration metric으로 쓰려면 temperature scaling 등 calibration protocol을 별도로 구현해야 한다.

### 6.3 `spot-diff`는 baseline이 아니다

- `spot-diff`는 VisA data helper/reorg 쪽이다.
- baseline runner와 혼동하지 않는다.

### 6.4 실제 baseline path 기준 채택

- PatchCore는 `external/patchcore-inspection`
- WinCLIP은 `external/WinClip`
- 현재 로컬 clone 상태를 project config 기준으로 맞추는 방향을 채택했다.

---

## 7. 바로 실행 가능한 명령

PatchCore smoke 재실행:

```bash
bash scripts/run_smoke.sh
```

PatchCore smoke 결과 평가:

```bash
python3 experiments/evaluate.py
```

테스트:

```bash
python3 -m unittest discover -s tests
```

문법/컴파일 확인:

```bash
python3 -m py_compile \
  experiments/evaluate.py \
  tests/test_evaluate.py \
  experiments/baselines/patchcore.py \
  tests/test_patchcore_wrapper.py
```

paper build placeholder 확인:

```bash
make paper
```

---

## 8. 앞으로 해야 할 일

### 8.1 먼저 할 일: 변경 정리와 commit 분리

추천 commit 분리:

1. PatchCore wrapper 구현
   - `experiments/baselines/patchcore.py`
   - `experiments/configs/baselines.yaml`
   - `scripts/run_smoke.sh`
   - `tests/test_patchcore_wrapper.py`

2. PatchCore smoke 결과 artifact 갱신
   - `results/latest/scores.csv`
   - `results/latest/latest_run.json`

3. evaluate.py 구현
   - `experiments/evaluate.py`
   - `tests/test_evaluate.py`
   - `results/latest/metrics.csv`
   - `results/latest/manifest.json`
   - `results/latest/tables/baseline_summary.tex`
   - `results/latest/figures/contamination_drop_placeholder.txt`

커밋 메시지는 AGENTS의 Lore Commit Protocol을 따르는 것이 좋다.

### 8.2 PatchCore smoke를 더 엄격하게 만들기

- `PATCHCORE_MAX_TEST_IMAGES`를 사용한 빠른 smoke와 full category smoke를 구분한다.
- smoke config에 `max_test_images`를 명시할지 결정한다.
- GPU/CPU 환경별 latency variance를 기록한다.
- `latest_run.json`에 runtime device, dependency versions, elapsed time 등을 더 넣을 수 있다.

### 8.3 evaluate.py 확장

현재는 single-run smoke evaluator다. 다음 확장이 필요하다.

- 여러 baseline row를 누적 평가하는 multi-run evaluator
- stream type별 metric 분리: `iid`, `bursty`
- contamination epsilon별 metric 분리: `0`, `0.01`, `0.05`
- CRD-lite 계산 구현
  - epsilon별 comparable run이 있어야 함
  - baseline/reference epsilon을 정해야 함
- calibration support
  - `none`
  - `temperature_scaling`
- table/figure artifact를 P0 matrix에 맞춰 확장

### 8.4 VisA 준비

- `data/visa/` 구조가 실험 runner가 기대하는 형태인지 확인한다.
- 필요하면 `external/spot-diff/utils/prepare_data.py`를 이용해 VisA를 정리한다.
- `data/README.md`와 실제 local layout이 일치하는지 확인한다.

### 8.5 나머지 baseline wrapper 구현

P0 scope baseline:

- RareCLIP
- WinCLIP
- AnomalyCLIP

각 baseline별로 해야 할 일:

1. upstream repo 실행 표면 분석
2. dependency 설치 방법 문서화
3. wrapper contract 구현
4. common score CSV schema로 output 맞추기
5. smoke test 추가
6. fake score 방지
7. `baselines.yaml` 업데이트

### 8.6 Full P0 실행 전 요구사항

Full P0 matrix:

- Datasets: MVTec AD, VisA
- Streams: iid, bursty
- Prevalence: 0.05
- Contamination epsilon: 0, 0.01, 0.05
- Baselines: RareCLIP, PatchCore, WinCLIP, AnomalyCLIP
- Memory policies: default/SCS, FIFO, Reservoir, Prototype-EMA
- Calibration: none, temperature scaling
- Metrics: AUROC, AUPR, ECE, latency, CRD-lite

필요 구현:

- real stream generator
- baseline-specific memory policy handling
- evaluation aggregation
- result archival policy
- paper table/figure generation

### 8.7 Paper gate

아직 paper gate는 열면 안 된다.

`manifest.paper_allowed=true` 조건:

- full P0 또는 명시적으로 승인된 measured experiment 완료
- 결과 schema 검증
- fake/placeholder row 없음
- metric 계산 검토 완료
- paper text/table/figure가 실제 결과와 일치하는지 검토 완료

현재 상태:

```json
"paper_allowed": false
```

이 상태를 유지해야 한다.
