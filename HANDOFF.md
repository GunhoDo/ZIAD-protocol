# HANDOFF — ZIAD 논문 구현 현재 상태

최종 갱신: 2026-05-23
프로젝트: Streaming Zero-Shot Industrial Anomaly Detection with CLIP / ZIAD Protocol

## 0. 절대 규칙

- `AGENTS.md`와 `docs/experiment-prd.md`가 canonical reference다.
- baseline URL/commit hash를 새로 지어내지 말 것. `experiments/configs/baselines.yaml`의 local clone 기준을 사용한다.
- fake metric 금지. placeholder는 `placeholder_not_measured`, 실제 측정은 `measured`/`measured_smoke`만 사용한다.
- 논문 게이트는 아직 닫힘: 모든 현재 산출물은 `paper_allowed=false` 유지.
- `.omx/`는 planning history이며 소스 오브 트루스가 아니다.

## 0.1 최근 완료: calibration-axis mini-matrix execution path

- 목표: 단일 `temperature_scaling` smoke를 넘어서 mini/full-category matrix runner가 calibration 축을 충돌 없이 생성/집계하도록 확장.
- 주요 수정:
  - `experiments/mini_matrix.py`가 `calibration` list 또는 `calibrations` list를 matrix 축으로 확장한다.
  - run id에 calibration 축이 필요한 경우 `_cal_none`, `_cal_temperature_scaling` suffix를 붙여 기존 run output 충돌을 방지한다.
  - `calibration_temperature`/`temperature`를 generated smoke config로 전달한다.
  - aggregate metrics/manifest가 calibration 축을 기록하고 CRD-lite grouping도 기존처럼 calibration별로 분리된다.
  - `experiments/category_sweep.py`가 sweep config의 `memory_policy`, `calibration`, `calibration_temperature`를 per-category mini-matrix config로 전달한다.
  - `experiments/configs/visa_winclip_temperature_mini_matrix.yaml` 추가.
- 실행 명령:
  - `python3 -m unittest tests.test_mini_matrix tests.test_category_sweep tests.test_calibration -v`
  - `bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_winclip_temperature_mini_matrix.yaml`
  - output sanity check: aggregate row count, calibration values, sidecar count, `paper_allowed=false`
  - `python3 -m unittest discover -v`
  - `python3 -m compileall experiments tests`
  - `git diff --check`
- 생성 outputs:
  - `results/latest/visa_temperature_mini_matrix/metrics_winclip_candle.csv`
  - `results/latest/visa_temperature_mini_matrix/manifest_winclip_candle.json`
  - `results/latest/visa_temperature_mini_matrix/crd_lite_winclip_candle.csv`
  - `results/latest/visa_temperature_mini_matrix/configs/*.yaml`
  - `results/latest/visa_temperature_mini_matrix/winclip_candle_*/*`
- 검증 결과:
  - VisA candle WinCLIP temperature mini-matrix: 12 aggregate metric rows.
  - 축: `iid/bursty × ε 0/0.01/0.05 × calibration none/temperature_scaling`.
  - all aggregate rows `status=measured_smoke`.
  - calibration values are `none` and `temperature_scaling`; temperature rows `6`.
  - calibration sidecars `6`, each generated from measured scores.
  - aggregate manifest records `run_count=12`, `calibration=['none','temperature_scaling']`, `paper_allowed=false`.
  - all per-run manifests keep `paper_allowed=false`.
  - unittest 72 tests OK, compileall OK, diff check OK.
- 제한:
  - 이 단계는 WinCLIP/VisA candle lightweight matrix 검증이다. full P0 calibration matrix는 아직 실행하지 않았다.
  - `temperature_scaling`은 여전히 smoke score postprocessor이며 calibration-set fitting이 아니다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.2 최근 완료: temperature_scaling smoke calibration path

- 목표: P0 calibration 값 `temperature_scaling`을 fake 없이 실제 smoke score 후처리 경로로 구현하고, 모든 산출물의 `paper_allowed=false`를 유지.
- 주요 수정:
  - `experiments/calibration.py` 추가: measured `anomaly_score`를 min-max probability로 정규화한 뒤 logit/temperature/sigmoid로 변환한다.
  - score schema는 그대로 유지한다: `stream_index,image_path,label,category,anomaly_score,latency_ms,peak_vram_mb,status`.
  - constant score는 `0.5`로 보정하고 metadata warning `constant_scores_temperature_scaled_to_0p5`를 기록한다.
  - `scripts/run_smoke.sh`가 wrapper inference 이후 calibration을 적용하고 `*_calibration.json` sidecar와 `latest_run.calibration_metadata`를 기록한다.
  - PatchCore/WinCLIP/AnomalyCLIP/RareCLIP wrapper contract가 `calibration=temperature_scaling`을 허용한다.
  - `experiments/p0_shards.py`가 P0 calibration 지원값을 `none,temperature_scaling`으로 표시하며 unsupported calibration은 빈 목록이다.
  - `experiments/configs/smoke_visa_winclip_temperature.yaml` 추가.
- 실행 명령:
  - `python3 -m unittest tests.test_calibration tests.test_baseline_contract tests.test_p0_shards -v`
  - `python3 -m compileall experiments tests`
  - `python3 experiments/p0_shards.py plan experiments/configs/p0.yaml --output results/latest/p0_shards/manifest.json`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip_temperature.yaml`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_winclip_temperature.csv --latest-run results/latest/latest_run_visa_winclip_temperature.json --output results/latest/metrics_visa_winclip_temperature.csv --manifest results/latest/manifest_visa_winclip_temperature.json`
  - metadata sanity check: rows, labels, unique paths, calibration metadata, `paper_allowed=false`
  - `python3 -m unittest discover -v`
  - `git diff --check`
- 생성 outputs:
  - `results/latest/stream_smoke_visa_winclip_temperature.json`
  - `results/latest/scores_visa_winclip_temperature.csv`
  - `results/latest/scores_visa_winclip_temperature_calibration.json`
  - `results/latest/metrics_visa_winclip_temperature.csv`
  - `results/latest/latest_run_visa_winclip_temperature.json`
  - `results/latest/manifest_visa_winclip_temperature.json`
  - `results/latest/p0_shards/manifest.json`
- 검증 결과:
  - WinCLIP VisA candle temperature smoke: 20 measured rows, unique image paths `20/20`, labels `[0,1]`.
  - calibration metadata records `method=temperature_scaling`, `temperature=2.0`, `rows_calibrated=20`, `paper_allowed=false`.
  - latest_run records `calibration=temperature_scaling` and embeds calibration metadata.
  - evaluated manifest keeps `paper_allowed=false`.
  - P0 shard manifest keeps `paper_allowed=false`; unsupported calibration is `[]`.
  - unittest 71 tests OK, compileall OK, diff check OK.
- 제한:
  - 이 calibration은 smoke-only score postprocessor다. calibration-set fitting이나 paper-ready probability calibration으로 해석하면 안 된다.
  - full P0 temperature-scaling matrix는 아직 실행하지 않았다.
  - 현재 ECE는 여전히 diagnostic이며 calibrated probability 결론으로 쓰지 않는다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.3 최근 완료: RareCLIP Prototype-EMA memory policy smoke path

- 목표: P0 memory policy 중 RareCLIP `Prototype-EMA`를 실제 online memory policy로 구현하고, fake metric 없이 `paper_allowed=false`를 유지.
- 주요 수정:
  - `experiments/baselines/rareclip.py`에서 RareCLIP `memory_policy=Prototype-EMA`를 허용한다.
  - RareCLIP patch sampler를 nearest-prototype EMA sampler로 교체한다.
  - online update 후 image-level `IF_memory`를 prototype 기준으로 줄이고, `score_memory`를 같은 assignment로 EMA 업데이트해 인덱스 정렬을 유지한다.
  - `AAIF_memory`도 bounded Prototype-EMA로 유지한다.
  - `prototype_ema_memory_size`와 `prototype_ema_alpha`가 config에서 제어된다.
  - `experiments/configs/smoke_visa_rareclip_prototype_ema.yaml` 추가.
  - `experiments/p0_shards.py`와 `results/latest/p0_shards/manifest.json`에서 RareCLIP/PatchCore current supported memory policy가 `default/SCS,FIFO,Reservoir,Prototype-EMA`로 표시된다.
  - 전체 P0 shard memory policy unsupported list는 이제 빈 목록이다.
- 실행 명령:
  - `python3 -m unittest tests.test_rareclip_wrapper tests.test_baseline_contract tests.test_p0_shards -v`
  - `python3 -m compileall experiments tests`
  - `python3 experiments/p0_shards.py plan experiments/configs/p0.yaml --output results/latest/p0_shards/manifest.json`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_rareclip_prototype_ema.yaml`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_rareclip_prototype_ema.csv --latest-run results/latest/latest_run_visa_rareclip_prototype_ema.json --output results/latest/metrics_visa_rareclip_prototype_ema.csv --manifest results/latest/manifest_visa_rareclip_prototype_ema.json`
  - `python3 -m unittest discover -v`
  - `git diff --check`
- 생성 outputs:
  - `results/latest/stream_smoke_visa_rareclip_prototype_ema.json`
  - `results/latest/scores_visa_rareclip_prototype_ema.csv`
  - `results/latest/metrics_visa_rareclip_prototype_ema.csv`
  - `results/latest/latest_run_visa_rareclip_prototype_ema.json`
  - `results/latest/manifest_visa_rareclip_prototype_ema.json`
  - `results/latest/p0_shards/manifest.json`
- 검증 결과:
  - RareCLIP Prototype-EMA VisA candle smoke: 20 measured rows, unique image paths `20/20`, labels `[0,1]`, stream warnings `0`.
  - latest_run records `memory_policy=Prototype-EMA`, `calibration=none`.
  - manifest keeps `paper_allowed=false`.
  - P0 shard manifest keeps `paper_allowed=false`; RareCLIP/PatchCore supported memory policies are `default/SCS,FIFO,Reservoir,Prototype-EMA`; unsupported memory policies are `[]`.
  - unittest 66 tests OK, compileall OK, diff check OK.
- 제한:
  - RareCLIP Prototype-EMA는 wrapper-level online memory bounding policy다. full P0 matrix와 paper-level 해석은 아직 아니다.
  - full P0 temperature-scaling matrix는 아직 미실행이다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.4 최근 완료: PatchCore Prototype-EMA feature-bank smoke path

- 목표: P0 memory policy 중 PatchCore `Prototype-EMA`를 실제 feature-bank compression sampler로 구현하고, fake metric 없이 `paper_allowed=false`를 유지.
- 주요 수정:
  - `experiments/baselines/patchcore.py`에서 PatchCore `memory_policy=Prototype-EMA`를 허용한다.
  - Prototype-EMA 실행 시 train/good feature stream을 nearest-prototype EMA 대표 feature bank로 압축한다.
  - `prototype_ema_memory_fraction`, `prototype_ema_alpha`, `prototype_ema_max_prototypes`, `prototype_ema_batch_size`가 config에서 제어된다.
  - 최초 구현의 `O(features × prototypes)` 비용을 피하려고 `max_prototypes` 상한과 batch assignment/update를 추가했다.
  - model cache key에 `prototype_ema_alpha`, `prototype_ema_max_prototypes`, `prototype_ema_batch_size`를 포함해 다른 PatchCore memory policy/cache와 섞이지 않게 한다.
  - `experiments/configs/smoke_visa_patchcore_prototype_ema.yaml` 추가.
  - `experiments/p0_shards.py`와 `results/latest/p0_shards/manifest.json`에서 PatchCore current supported memory policy가 `default/SCS,FIFO,Reservoir,Prototype-EMA`로 표시되고, PatchCore shard unsupported memory policy는 빈 목록이다.
  - 전체 P0 shard memory policy unsupported list에는 이 단계 당시 RareCLIP 미지원 때문에 `Prototype-EMA`가 남았다. 이후 RareCLIP Prototype-EMA도 별도 커밋에서 구현됐다.
- 실행 명령:
  - `python3 -m unittest tests.test_patchcore_wrapper tests.test_baseline_contract tests.test_p0_shards -v`
  - `python3 -m compileall experiments tests`
  - `python3 experiments/p0_shards.py plan experiments/configs/p0.yaml --output results/latest/p0_shards/manifest.json`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_patchcore_prototype_ema.yaml`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_patchcore_prototype_ema.csv --latest-run results/latest/latest_run_visa_patchcore_prototype_ema.json --output results/latest/metrics_visa_patchcore_prototype_ema.csv --manifest results/latest/manifest_visa_patchcore_prototype_ema.json`
- 생성 outputs:
  - `results/latest/stream_smoke_visa_patchcore_prototype_ema.json`
  - `results/latest/scores_visa_patchcore_prototype_ema.csv`
  - `results/latest/metrics_visa_patchcore_prototype_ema.csv`
  - `results/latest/latest_run_visa_patchcore_prototype_ema.json`
  - `results/latest/manifest_visa_patchcore_prototype_ema.json`
  - `results/latest/p0_shards/manifest.json`
- 검증 결과:
  - PatchCore Prototype-EMA VisA candle smoke: 20 measured rows, unique image paths `20/20`, labels `[0,1]`, stream warnings `0`.
  - latest_run records `memory_policy=Prototype-EMA`, `calibration=none`.
  - manifest keeps `paper_allowed=false`.
  - P0 shard manifest keeps `paper_allowed=false`; PatchCore supported memory policies are `default/SCS,FIFO,Reservoir,Prototype-EMA`; PatchCore unsupported memory policies are `[]`; 이 단계 당시 overall unsupported memory policies are still `Prototype-EMA` because RareCLIP lacked it.
- 제한:
  - PatchCore Prototype-EMA는 train/good feature bank compression policy다. true online PatchCore update latency로 해석하면 안 된다.
  - 이 단계 당시 RareCLIP Prototype-EMA와 temperature scaling은 아직 미지원이었다. 이후 RareCLIP Prototype-EMA와 temperature_scaling smoke path는 별도 커밋에서 구현됐다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.5 최근 완료: PatchCore Reservoir feature-bank smoke path

- 목표: P0 memory policy 중 PatchCore `Reservoir`를 실제 feature-bank sampler로 구현하고, fake metric 없이 `paper_allowed=false`를 유지.
- 주요 수정:
  - `experiments/baselines/patchcore.py`에서 PatchCore `memory_policy=Reservoir`를 허용한다.
  - Reservoir 실행 시 train/good feature bank를 seeded reservoir sampler로 bounded selection한다.
  - `reservoir_memory_fraction`과 `reservoir_seed`가 config에서 제어된다.
  - model cache key에 `memory_policy`와 `reservoir_seed`를 포함해 default/SCS, FIFO, Reservoir cache가 섞이지 않게 한다.
  - `experiments/configs/smoke_visa_patchcore_reservoir.yaml` 추가.
  - `experiments/p0_shards.py`와 `results/latest/p0_shards/manifest.json`에서 PatchCore/RareCLIP current supported memory policy가 `default/SCS,FIFO,Reservoir`로 표시된다.
  - P0 shard memory policy unsupported list에는 이제 `Prototype-EMA`만 남는다.
- 실행 명령:
  - `python3 -m unittest tests.test_patchcore_wrapper tests.test_baseline_contract tests.test_p0_shards -v`
  - `python3 -m compileall experiments tests`
  - `python3 experiments/p0_shards.py plan experiments/configs/p0.yaml --output results/latest/p0_shards/manifest.json`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_patchcore_reservoir.yaml`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_patchcore_reservoir.csv --latest-run results/latest/latest_run_visa_patchcore_reservoir.json --output results/latest/metrics_visa_patchcore_reservoir.csv --manifest results/latest/manifest_visa_patchcore_reservoir.json`
  - `python3 -m unittest discover -v`
  - `git diff --check`
- 생성 outputs:
  - `results/latest/stream_smoke_visa_patchcore_reservoir.json`
  - `results/latest/scores_visa_patchcore_reservoir.csv`
  - `results/latest/metrics_visa_patchcore_reservoir.csv`
  - `results/latest/latest_run_visa_patchcore_reservoir.json`
  - `results/latest/manifest_visa_patchcore_reservoir.json`
  - `results/latest/p0_shards/manifest.json`
- 검증 결과:
  - PatchCore Reservoir VisA candle smoke: 20 measured rows, unique image paths `20/20`, labels `[0,1]`, stream warnings `0`.
  - latest_run records `memory_policy=Reservoir`, `calibration=none`.
  - manifest keeps `paper_allowed=false`.
  - P0 shard manifest keeps `paper_allowed=false`, PatchCore/RareCLIP supported memory policies are `default/SCS,FIFO,Reservoir`, unsupported memory policies are `Prototype-EMA`.
  - unittest 61 tests OK, compileall OK, diff check OK.
- 제한:
  - PatchCore Reservoir는 train/good feature bank selection policy다. true online PatchCore update latency로 해석하면 안 된다.
  - 이 단계 당시 PatchCore Prototype-EMA와 temperature scaling은 아직 미지원이었다. 이후 PatchCore Prototype-EMA와 temperature_scaling smoke path는 별도 커밋에서 구현됐다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.6 최근 완료: RareCLIP Reservoir memory policy smoke path

- 목표: P0 memory policy 중 RareCLIP `Reservoir`를 실제 online memory policy로 구현하고, fake metric 없이 `paper_allowed=false`를 유지.
- 주요 수정:
  - `experiments/baselines/rareclip.py`에서 RareCLIP `memory_policy=Reservoir`를 허용한다.
  - Reservoir 실행 시 upstream RareCLIP patch sampler를 seeded reservoir sampler로 교체한다.
  - online update 후 image-level `score_memory`, `IF_memory`, `AAIF_memory`를 같은 seeded reservoir policy로 bounded 유지한다.
  - upstream PSM layout(`region rows × feature refs`)을 고려해 feature reference column만 reservoir index로 자르고, square layout일 때만 row도 함께 자른다.
  - `reservoir_memory_size`와 `reservoir_seed`가 config에서 제어된다.
  - `experiments/configs/smoke_visa_rareclip_reservoir.yaml` 추가.
  - `experiments/p0_shards.py`와 `results/latest/p0_shards/manifest.json`에서 RareCLIP current supported memory policy가 `default/SCS,FIFO,Reservoir`로 표시된다. 이후 PatchCore Reservoir도 구현되어 전체 memory policy unsupported list에는 `Prototype-EMA`만 남는다.
- 실행 명령:
  - `python3 -m unittest tests.test_rareclip_wrapper tests.test_baseline_contract tests.test_p0_shards -v`
  - `python3 -m compileall experiments tests`
  - `python3 experiments/p0_shards.py plan experiments/configs/p0.yaml --output results/latest/p0_shards/manifest.json`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_rareclip_reservoir.yaml`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_rareclip_reservoir.csv --latest-run results/latest/latest_run_visa_rareclip_reservoir.json --output results/latest/metrics_visa_rareclip_reservoir.csv --manifest results/latest/manifest_visa_rareclip_reservoir.json`
  - `python3 -m unittest discover -v`
  - `git diff --check`
- 생성 outputs:
  - `results/latest/stream_smoke_visa_rareclip_reservoir.json`
  - `results/latest/scores_visa_rareclip_reservoir.csv`
  - `results/latest/metrics_visa_rareclip_reservoir.csv`
  - `results/latest/latest_run_visa_rareclip_reservoir.json`
  - `results/latest/manifest_visa_rareclip_reservoir.json`
  - `results/latest/p0_shards/manifest.json`
- 검증 결과:
  - RareCLIP Reservoir VisA candle smoke: 20 measured rows, unique image paths `20/20`, labels `[0,1]`, stream warnings `0`.
  - latest_run records `memory_policy=Reservoir`, `calibration=none`.
  - manifest keeps `paper_allowed=false`.
  - unittest 59 tests OK, compileall OK, diff check OK.
- 제한:
  - 이 단계 당시 Reservoir는 RareCLIP wrapper에 먼저 구현됐고, 이후 PatchCore Reservoir도 별도 커밋에서 구현됐다.
  - 이 단계 당시 Prototype-EMA와 temperature scaling은 아직 미지원이었다. 이후 RareCLIP/PatchCore Prototype-EMA와 temperature_scaling smoke path는 별도 커밋에서 구현됐다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.7 최근 완료: PatchCore FIFO feature-bank smoke path

- 목표: P0 memory policy 중 PatchCore `FIFO`를 실제 feature-bank sampler로 구현하고, fake metric 없이 `paper_allowed=false`를 유지.
- 주요 수정:
  - `experiments/baselines/patchcore.py`에서 PatchCore도 `memory_policy=FIFO`를 허용한다.
  - FIFO 실행 시 PatchCore feature sampler를 oldest-first eviction 의미의 newest-retention sampler로 교체한다.
  - `fifo_memory_fraction`이 feature bank 보존 비율을 제어한다.
  - model cache key에 `memory_policy`를 포함해 default/SCS cache와 FIFO cache가 섞이지 않게 한다.
  - `experiments/configs/smoke_visa_patchcore_fifo.yaml` 추가.
  - `experiments/p0_shards.py`와 `results/latest/p0_shards/manifest.json`에서 PatchCore/RareCLIP current supported memory policy가 `default/SCS,FIFO`로 표시된다.
  - `.gitignore`는 PatchCore model cache 계열을 계속 제외하도록 정리했다.
- 실행 명령:
  - `python3 -m unittest tests.test_patchcore_wrapper tests.test_baseline_contract tests.test_p0_shards -v`
  - `python3 -m compileall experiments tests`
  - `python3 experiments/p0_shards.py plan experiments/configs/p0.yaml --output results/latest/p0_shards/manifest.json`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_patchcore_fifo.yaml`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_patchcore_fifo.csv --latest-run results/latest/latest_run_visa_patchcore_fifo.json --output results/latest/metrics_visa_patchcore_fifo.csv --manifest results/latest/manifest_visa_patchcore_fifo.json`
  - `python3 -m unittest discover -v`
  - `git diff --check`
- 생성 outputs:
  - `results/latest/stream_smoke_visa_patchcore_fifo.json`
  - `results/latest/scores_visa_patchcore_fifo.csv`
  - `results/latest/metrics_visa_patchcore_fifo.csv`
  - `results/latest/latest_run_visa_patchcore_fifo.json`
  - `results/latest/manifest_visa_patchcore_fifo.json`
  - `results/latest/p0_shards/manifest.json`
- 검증 결과:
  - PatchCore FIFO VisA candle smoke: 20 measured rows, unique image paths `20/20`, labels `[0,1]`, stream warnings `0`.
  - latest_run records `memory_policy=FIFO`, `calibration=none`.
  - manifest keeps `paper_allowed=false`.
  - unittest 56 tests OK, compileall OK, diff check OK.
- 제한:
  - PatchCore FIFO는 train/good feature bank selection policy다. true online PatchCore update latency로 해석하면 안 된다.
  - 이 단계 당시 PatchCore Reservoir/Prototype-EMA와 temperature scaling은 아직 미지원이었다. 이후 PatchCore Reservoir/Prototype-EMA와 temperature_scaling smoke path는 별도 커밋에서 구현됐다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.8 최근 완료: RareCLIP FIFO memory policy smoke path

- 목표: P0 memory policy 중 하나를 실제 wrapper 동작으로 승격하되, fake metric 없이 `paper_allowed=false`를 유지.
- 주요 수정:
  - `experiments/baselines/rareclip.py`에서 RareCLIP만 `memory_policy=FIFO`를 허용한다.
  - FIFO 실행 시 upstream RareCLIP patch sampler를 oldest-first retention으로 교체한다.
  - online update 후 `score_memory`, `IF_memory`, `AAIF_memory`, `PFM`, `PSM`을 `fifo_memory_size` 기준으로 trimming한다.
  - upstream RareCLIP의 list/list memory layout과 test fake model의 dict layout을 모두 테스트한다.
  - `experiments/configs/smoke_visa_rareclip_fifo.yaml` 추가.
  - `experiments/p0_shards.py`와 `results/latest/p0_shards/manifest.json`에서 RareCLIP current supported memory policy가 `default/SCS,FIFO`로 표시됐다.
- 실행 명령:
  - `python3 -m unittest tests.test_rareclip_wrapper tests.test_baseline_contract tests.test_p0_shards -v`
  - `python3 -m compileall experiments tests`
  - `python3 experiments/p0_shards.py plan experiments/configs/p0.yaml --output results/latest/p0_shards/manifest.json`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_rareclip_fifo.yaml`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_rareclip_fifo.csv --latest-run results/latest/latest_run_visa_rareclip_fifo.json --output results/latest/metrics_visa_rareclip_fifo.csv --manifest results/latest/manifest_visa_rareclip_fifo.json`
  - `python3 -m unittest discover -v`
  - `git diff --check`
- 생성 outputs:
  - `results/latest/stream_smoke_visa_rareclip_fifo.json`
  - `results/latest/scores_visa_rareclip_fifo.csv`
  - `results/latest/metrics_visa_rareclip_fifo.csv`
  - `results/latest/latest_run_visa_rareclip_fifo.json`
  - `results/latest/manifest_visa_rareclip_fifo.json`
  - `results/latest/p0_shards/manifest.json`
- 검증 결과:
  - RareCLIP FIFO VisA candle smoke: 20 measured rows, unique image paths `20/20`, labels `[0,1]`, stream warnings `0`.
  - latest_run records `memory_policy=FIFO`, `calibration=none`.
  - manifest keeps `paper_allowed=false`.
  - unittest 53 tests OK, compileall OK, diff check OK.
- 제한:
  - 이 단계 당시 FIFO는 RareCLIP wrapper에 먼저 구현됐고, 이후 PatchCore FIFO도 별도 커밋에서 구현됐다.
  - 이 단계 당시 Reservoir, Prototype-EMA, temperature scaling은 계속 미지원이었다. 이후 FIFO/Reservoir/Prototype-EMA와 temperature_scaling smoke path는 별도 커밋에서 구현됐다.
  - 이 output은 smoke evidence이며 paper result가 아니다.

## 0.9 최근 완료: memory_policy/calibration execution contract

- 목표: P0 shard에서 미구현 `memory_policy`/`calibration` 값이 조용히 default로 대체되지 않도록 실행 전 contract를 고정.
- 주요 수정:
  - `experiments/baselines/base.py`에 `validate_execution_contract()` 추가.
  - PatchCore/RareCLIP/WinCLIP/AnomalyCLIP wrapper가 실행 시작 시 contract를 검증한다.
  - 이 단계 당시 지원값은 `memory_policy=default/SCS`, `calibration=none`뿐이었다. 이후 memory policy와 `temperature_scaling` 지원이 별도 커밋에서 추가됐다.
  - `scripts/run_smoke.sh`가 `memory_policy`와 `calibration`을 latest_run provenance에 기록한다.
  - `experiments/mini_matrix.py`가 matrix config의 `memory_policy`/`calibration`을 generated smoke config로 전달한다.
  - `tests/test_baseline_contract.py` 추가, `tests/test_mini_matrix.py` 보강.
- 실행 명령:
  - `python3 -m unittest tests.test_baseline_contract tests.test_mini_matrix tests.test_patchcore_wrapper tests.test_rareclip_wrapper tests.test_winclip_wrapper tests.test_anomalyclip_wrapper -v`
  - `bash scripts/run_smoke.sh experiments/configs/smoke_visa_winclip.yaml`
  - `bash scripts/run_smoke.sh /tmp/ziad-policy.../unsupported.yaml` — expected failure for `memory_policy=FIFO`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_winclip.csv --latest-run results/latest/latest_run_visa_winclip.json --output results/latest/metrics_visa_winclip.csv --manifest results/latest/manifest_visa_winclip.json`
  - `python3 experiments/evaluate.py --scores-csv results/latest/scores_visa_patchcore.csv --latest-run results/latest/latest_run_visa_patchcore.json --output results/latest/metrics_visa_patchcore.csv --manifest results/latest/manifest_visa_patchcore.json`
  - `python3 -m unittest discover -v`
  - `python3 -m compileall experiments tests`
  - `git diff --check`
- 갱신된 trackable smoke outputs:
  - `results/latest/latest_run_visa_winclip.json` — `memory_policy=default/SCS`, `calibration=none`, `paper_allowed=false`.
  - `results/latest/metrics_visa_winclip.csv` / `scores_visa_winclip.csv` — contract verification용 fresh measured smoke output.
- 세부 검증:
  - `memory_policy=FIFO` smoke config fails with explicit RuntimeError and does not run as default/SCS.
  - normal VisA WinCLIP smoke still produces 20 measured rows.
  - latest_run records `memory_policy=default/SCS`, `calibration=none`.
  - unittest 48 tests OK, compileall OK, diff check OK.
- 제한:
  - 이 단계 당시 FIFO/Reservoir/Prototype-EMA와 temperature scaling은 아직 구현되지 않았고 명시적 거부만 했다. 이후 FIFO/Reservoir, RareCLIP/PatchCore Prototype-EMA, temperature_scaling smoke path는 별도 커밋에서 구현됐다.
  - 이 단계는 execution contract hardening이며 full P0 실행이 아니다.

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
- VisA PatchCore mini-matrix 구성 완료:
  - config: `experiments/configs/visa_patchcore_mini_matrix.yaml`
  - dataset root: `data/visa/1cls`
  - category: `candle`
  - stream/epsilon: `iid`, `bursty` × ε=`0`, `0.01`, `0.05`, length=20
  - `baseline_options` forwards `sampler: random` to generated smoke configs for bounded CPU runtime
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
- VisA full-category PatchCore smoke sweep 구성 완료:
  - config: `experiments/configs/visa_full_category_sweep_patchcore.yaml`
  - runner: `scripts/run_visa_full_category_sweep_patchcore.sh`
  - dataset root: `data/visa/1cls`
  - categories: all 12 local VisA categories (`candle,capsules,cashew,chewinggum,fryum,macaroni1,macaroni2,pcb1,pcb2,pcb3,pcb4,pipe_fryum`)
  - baseline: PatchCore only
  - stream/epsilon: `iid`, ε=`0`, length=20
  - `baseline_options` forwards `sampler: identity` to avoid slow upstream coreset subsampling during smoke
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
- VisA PatchCore mini-matrix 6 runs 실행 완료:
  - config: `experiments/configs/visa_patchcore_mini_matrix.yaml`
  - command: `bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_patchcore_mini_matrix.yaml`
  - aggregate metrics: `results/latest/visa_patchcore_mini_matrix/metrics_patchcore_candle.csv`
  - CRD-lite summary: `results/latest/visa_patchcore_mini_matrix/crd_lite_patchcore_candle.csv`
  - aggregate manifest: `results/latest/visa_patchcore_mini_matrix/manifest_patchcore_candle.json`
  - rows: 6 measured_smoke rows
  - stream types: `iid`, `bursty`
  - epsilon: `0.0`, `0.01`, `0.05`
  - all generated streams have unique paths `20/20`, labels `[0, 1]`, bursty streams record contiguous anomaly block metadata
  - warning count: 2 expected `target_fraction_adjusted` warnings for ε=`0.01`
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
bash scripts/run_baseline_mini_matrix.sh experiments/configs/visa_patchcore_mini_matrix.yaml
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
bash scripts/run_visa_full_category_stream_matrix_patchcore.sh
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
- VisA WinCLIP iid temperature-scaling smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, calibration metadata rows `20`, evaluated manifest `paper_allowed=false`
- VisA WinCLIP temperature mini-matrix: 12 rows, dataset `VisA`, category `candle`, stream types `iid/bursty`, epsilon `0/0.01/0.05`, calibration `none/temperature_scaling`, all `measured_smoke`, 6 calibration sidecars, aggregate manifest `paper_allowed=false`
- VisA WinCLIP mini-matrix: 6 rows, dataset `VisA`, category `candle`, stream types `iid/bursty`, epsilon `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, aggregate manifest `paper_allowed=false`
- VisA PatchCore mini-matrix: 6 rows, dataset `VisA`, category `candle`, stream types `iid/bursty`, epsilon `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, warning count 2, aggregate manifest `paper_allowed=false`
- VisA WinCLIP bursty standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, contiguous anomaly block lengths `[1]`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA AnomalyCLIP iid standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA RareCLIP iid standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA PatchCore iid standalone smoke: 20 rows, dataset `VisA`, category `candle`, labels `[0, 1]`, unique paths `20/20`, all `measured`, evaluated manifest `paper_allowed=false`
- VisA full-category WinCLIP sweep: 12 rows, all 12 local VisA categories, all `measured_smoke`, all generated streams unique paths `20/20`, labels `[0, 1]`, aggregate manifest `paper_allowed=false`
- VisA full-category AnomalyCLIP sweep: 12 rows, all 12 local VisA categories, all `measured_smoke`, all generated streams unique paths `20/20`, labels `[0, 1]`, aggregate manifest `paper_allowed=false`
- VisA full-category RareCLIP sweep: 12 rows, all 12 local VisA categories, all `measured_smoke`, all generated streams unique paths `20/20`, labels `[0, 1]`, aggregate manifest `paper_allowed=false`
- VisA full-category WinCLIP stream/epsilon matrix: 72 rows, all 12 local VisA categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, warning count 24, aggregate manifest `paper_allowed=false`
- VisA full-category AnomalyCLIP stream/epsilon matrix: 72 rows, all 12 local VisA categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, warning count 24, aggregate manifest `paper_allowed=false`
- VisA full-category PatchCore stream/epsilon matrix: 72 rows, all 12 local VisA categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, bursty contiguous anomaly block check passed, aggregate manifest `paper_allowed=false`
- VisA full-category RareCLIP stream/epsilon matrix: 72 rows, all 12 local VisA categories × `iid/bursty` × ε `0/0.01/0.05`, all `measured_smoke`, CRD-lite all `derived_smoke`, generated streams unique paths `20/20`, labels `[0, 1]`, warning count 24, aggregate manifest `paper_allowed=false`

## 3. 지금 논문 관점에서 어디까지 왔나

현재는 **MVTec AD와 VisA 모두에서 4개 baseline(PatchCore/WinCLIP/AnomalyCLIP/RareCLIP)의 all-category stream/epsilon smoke matrix가 동작함을 입증한 단계**다.

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
13. VisA all-12-category `iid/bursty × ε 0/0.01/0.05` length=20은 WinCLIP, AnomalyCLIP, RareCLIP, PatchCore로 실제 image-level score를 생성했다.
14. VisA candle iid ε=0 length=20은 PatchCore에서도 실제 image-level score를 생성했다.
15. VisA candle `iid/bursty × ε 0/0.01/0.05` length=20은 PatchCore에서도 실제 image-level score를 생성했다.
16. `temperature_scaling`은 smoke runner 공통 score postprocessor로 구현됐고, VisA candle WinCLIP iid ε=0 length=20에서 실제 measured score 20개를 보정했다.
17. mini/full-category matrix 생성기는 calibration 축을 전달할 수 있으며, VisA candle WinCLIP `iid/bursty × ε 0/0.01/0.05 × calibration none/temperature_scaling` 12-run matrix가 실제 measured smoke로 통과했다.

하지만 아직 **논문 결과 단계는 아니다**.

부족한 것:

- full P0 matrix 미실행
- P0 shard manifest는 생성됐고 `temperature_scaling` smoke postprocessor 및 calibration-axis mini-matrix는 구현됐지만, full P0 calibration matrix는 아직 미실행
- CRD-lite는 smoke aggregate summary로 구현됨; full P0/VisA 검증과 paper 해석은 미완
- paper table pipeline은 smoke evidence table만 생성함; full matrix 기반 table/figure는 아직 아님
- review 전이므로 `paper_allowed=true` 금지

## 4. 다음 에이전트가 빠르게 해야 할 일

### 1순위 — full-category calibration matrix를 shard 단위로 실행

smoke-level `temperature_scaling` 후처리와 mini/full-category config propagation contract는 고정됐다. 다음은 가장 짧은 shard부터 full-category calibration matrix를 `paper_allowed=false`로 실행하고, runtime이 큰 baseline은 별도 shard로 분리한다.

### 2순위 — paper table/figure pipeline 확장

현재 table renderer는 smoke evidence만 다룬다. P0 shard aggregate가 생기면 full matrix 기반 table/figure 입력 contract를 먼저 고정하고, `paper_allowed=true` 승격은 리뷰 후 별도 커밋으로만 한다.

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
- VisA all-category stream/epsilon matrices와 candle smoke들은 adapter/scoring path 검증용이다. VisA 전체 P0 결과나 논문 결론으로 해석 금지.
- `render_paper_tables.py`는 결과를 “논문 결론”으로 승격하지 않는다. 현재 생성 표는 smoke evidence table이며 `paper_allowed=false`를 명시한다.
