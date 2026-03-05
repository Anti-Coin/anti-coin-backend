# Coin Predict Task Board (Active)

- Last Updated: 2026-03-05
- Rule: 활성 태스크만 유지하고, 완료 상세 이력은 Archive로 분리
- Full Phase A History: `docs/archive/phase_a/TASKS_MINIMUM_UNITS_PHASE_A_FULL_2026-02-12.md`
- Full Phase B History: `docs/archive/phase_b/TASKS_MINIMUM_UNITS_PHASE_B_FULL_2026-02-19.md`
- Full Phase C History: `docs/archive/phase_c/TASKS_MINIMUM_UNITS_PHASE_C_FULL_2026-02-20.md`

## 0. Priority
1. P0: 안정성/무결성 즉시 영향
2. P1: 확장성/운영성 핵심 영향
3. P2: 품질/가독성/자동화 개선

## 1. Milestone Snapshot
1. Phase A(Reliability Baseline) 완료 (2026-02-12)
2. Phase B(Timeframe Expansion) 완료 (2026-02-19)
3. Phase C(Scale and Ops) 완료 (2026-02-20)
4. `R-005` 완료 (2026-02-19): SLA-lite baseline을 user plane availability 중심으로 고정
5. `C-004` 완료 (2026-02-20): 학습 one-shot 실행 경계(`worker-train`) 잠금
6. `D-018` 완료 (2026-02-21): `1d/1w/1M` direct fetch 단일 경로 전환 및 downsample/lineage 코드 비참조화
7. `D-019` 완료 (2026-02-21): static 파일 self-heal + 장주기 full-fill/full-serving 정렬
8. 현재 활성 구현 트랙은 Phase D(Model Evolution)이다.
9. `D-020` 완료 (2026-02-24): 1d/1w/1M full-fill 복구 + 재발 방지 가드 정렬

## 2. Active Tasks
### Rebaseline (Post-Phase A)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| R-001 | P0 | B/C/D Phase 목적 및 Exit 조건 재검증 | done (2026-02-12) | B/C/D Objective/Exit 재정의가 `docs/PLAN_LIVING_HYBRID.md`에 반영됨 |
| R-002 | P0 | B/C/D 태스크 재세분화(리스크 반영) | done (2026-02-12) | 활성 태스크별 `why/failure/verify/rollback` 설계 카드가 정렬됨 |
| R-003 | P0 | 교차 Phase 의존성/우선순위 재정렬 | done (2026-02-12) | Option A/B 비교 및 채택 기준선 확정 |
| R-004 | P1 | Phase B kickoff 구현 묶음 확정 | done (2026-02-12) | `B-002 -> B-003` kickoff 묶음과 검증/롤백 경계 확정 |
| R-005 | P1 | SLA-lite 지표 baseline 정의 | done (2026-02-19) | availability/alert miss/MTTR-stale 공식/데이터 소스/산출 주기 잠금 |

### Phase B (Timeframe Expansion) - Summary
| ID | Priority | Task | Status |
|---|---|---|---|
| B-001 | P1 | timeframe tier 정책 매트릭스 확정(수집/보존/서빙/예측) | done (2026-02-17) |
| B-002 | P1 | 파일 네이밍 규칙 통일 | done (2026-02-13) |
| B-003 | P1 | history/prediction export timeframe-aware 전환 | done (2026-02-13) |
| B-004 | P1 | manifest 파일 생성 | done (2026-02-13) |
| B-005 | P2 | `/history`/`/predict` fallback 정리(sunset) | done (2026-02-19) |
| B-006 | P1 | 저장소 예산 가드(50GB) + retention/downsample 실행 | done (2026-02-13) |
| B-007 | P2 | 운영 대시보드(admin) timeframe 확장 | done (2026-02-19) |
| B-008 | P2 | FE 심볼 노출 게이트 연동(`hidden_backfilling`) | done (2026-02-19, sunset scope close) |

### Phase C (Scale and Ops) - Summary
| ID | Priority | Task | Status |
|---|---|---|---|
| C-001 | P1 | 심볼 목록 확장 자동화 | done (2026-02-20) |
| C-002 | P1 | 실행시간/실패율 메트릭 수집 | done (2026-02-17) |
| C-003 | P2 | 부하 테스트 시나리오 업데이트 | done (2026-02-20) |
| C-004 | P2 | 모델 학습 잡 분리 초안 | done (2026-02-20) |
| C-005 | P1 | pipeline worker 역할 분리 | done (2026-02-17) |
| C-006 | P1 | timeframe 경계 기반 scheduler 전환 | done (2026-02-17) |
| C-007 | P1 | 신규 candle 감지 게이트 결합 | done (2026-02-17) |
| C-008 | P1 | `1h` underfill RCA + temporary guard sunset 결정 | done (2026-02-17) |
| C-009 | P1 | monitor Influx-JSON consistency timeframe-aware 보강 | done (2026-02-19) |
| C-010 | P2 | orchestrator 가독성 정리(`pipeline_worker.py` 제어면 경계 단순화) | done (2026-02-19) |
| C-011 | P1 | boundary scheduler 재시작 catch-up 보강 | done (2026-02-19) |
| C-012 | P2 | 디렉토리/파일 재배치 계약 정리 | done (2026-02-20) |
| C-013 | P2 | `pipeline_worker.py` 저수준 가독성 분해(timeboxed) | done (2026-02-20) |
| C-014 | P1 | derived TF skip 경로 publish starvation 완화 | done (2026-02-20) |
| C-015 | P1 | prediction status fallback 경계 강화 | done (2026-02-20) |
| C-016 | P2 | stale 장기 지속 재시도/승격 정책 정비 | done (2026-02-20) |

### Phase D (Model Evolution) - Active
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| D-001 | P1 | 모델 계약 명시화(`fit/predict/save/load` 입출력 계약 문서화) | done (2026-02-26) | Prophet 경로 기준 계약을 `docs/MODEL_CONTRACT.md`로 고정하고, 회귀 테스트 `tests/test_model_contract.py`로 `fit` 입력 정규화(`ds` timezone-naive), `load` 우선순위(canonical > legacy), `predict` 산출물(JSON/Influx schema)을 잠금했다. |
| D-002 | P1 | 모델 메타데이터/버전 스키마 정의 | done (2026-02-26) | 모델 sidecar metadata 경로(`model_{symbol}_{timeframe}.meta.json`)와 스키마(v1)를 `docs/MODEL_METADATA_SCHEMA.md`로 고정하고, `train_model` 저장 경로에서 `schema_version/run_id/trained_at/row_count/data_range/model_version/snapshot_path/status` 기록을 강제했다. 회귀 테스트 `tests/test_train_model.py::test_train_and_save_persists_model_metadata_schema` 통과. |
| D-003 | P1 | Shadow 추론 파이프라인 도입 | open | shadow 결과 생성, 사용자 서빙 미반영. **분해 예정**(D-003a: Shadow 실행 경로, D-003b: Shadow 결과 저장, D-003c: 격리 보장) |
| D-004 | P1 | Champion vs Shadow 평가 리포트 | open | 최소 1개 지표 일별 산출 |
| D-005 | P1 | 승격 게이트 정책 구현 | open | 자동 승격 전 게이트를 평가하고, 미달 시 champion 교체를 차단한다(`fail-closed`). 승격/차단 결과는 로그/메타데이터로 추적 가능해야 한다. |
| D-006 | P2 | 자동 재학습 잡(수동 트리거) | open | 운영자 수동 재학습 가능 |
| D-007 | P2 | 자동 재학습 스케줄링 | open | 설정 기반 주기 재학습이 가능하고, `D-005` 게이트 통과 시에만 자동 승격 루프가 완료된다. |
| D-008 | P2 | 모델 롤백 절차/코드 추가 | open | 이전 champion 복귀 가능 |
| D-009 | P2 | Drift 알림 연동 | open | 임계 초과 시 경고 발송 |
| D-010 | **P0** | 장기 timeframe 최소 샘플 gate 구현 | **done (2026-02-21)** | `MIN_SAMPLE_BY_TIMEFRAME` config + `count_ohlcv_rows` query + `run_prediction_and_save` gate 삽입, 회귀 테스트 140 passed |
| D-011 | P3 (Hold) | Model Coverage Matrix + Fallback Resolver 구현 | open | (보류) 현재 런타임은 `symbol+timeframe canonical` 아티팩트 경계를 유지한다. shared/dedicated resolver 및 승격 정책은 `D-003~D-005` 이후 재개한다. |
| D-012 | **P0** | 학습 데이터 SoT 정렬 + Chunk 기반 추출 안전장치 (OOM 방지) | done (2026-02-26) | 학습 입력이 Influx SoT 기준으로 고정되고, 데이터를 한 번에 메모리에 올리지 않도록 `chunk/pagination` 기반 추출을 적용했다. 모델 추적은 MLflow `SQLite backend`로 잠그고, 학습 반영은 `symbol+timeframe partial-success` 정책을 적용했다. snapshot은 `latest 1개`만 유지하며 run metadata(`run_id`, `data_range`, `row_count`, `model_version`)를 기록한다. Prophet `ds` timezone-naive 정규화 회귀 테스트를 추가했고, `worker-train` ops-train 스모크를 통과했다. |
| D-013 | P1 | 재학습 트리거 정책 정의(1차 시간 기반, 2차 이벤트 선택) | in_progress (2026-03-03) | 시간 기반 정책을 `00:35 UTC` daily scheduler + TF due matrix(`1h/1d=매일`, `1w=월요일`, `1M=매월 1일`)로 문서/코드에 고정하고, 재시도 `N=2`(backoff `10m -> 30m`) 및 no-overlap 선행 조건을 잠근다. 이벤트 카탈로그(`EVT_PRICE_SHOCK_1H`, `EVT_VOL_SPIKE_24H`, `EVT_MODEL_DRIFT`)는 임계치/가드(`2회 연속`, `cooldown 24h`, `min_model_age 12h`)를 문서에 고정하되 실행은 보류한다. |
| D-014 | P1 | 학습 실행 no-overlap/락 가드 | open | 학습 동시 실행 차단, stale lock 복구 규칙, 회귀 테스트가 고정됨 |
| D-015 | P2 | 학습 실행 관측성/알림 baseline | open | 학습 실행시간/성공-실패/최근성 메트릭과 장애 알림 기준이 운영 문서와 함께 반영됨 |
| D-016 | P2 | `pipeline_worker.py` 상태 관리 분리(`worker_state.py`) | open | watermark/prediction_health/symbol_activation/runtime_metrics load/save/upsert가 `scripts/worker_state.py`로 이동, 회귀 테스트 통과 |
| D-017 | P2 | `pipeline_worker.py` `_ctx()` 래퍼 패턴 해소 | open | 테스트가 `workers.*` 직접 참조로 전환되고 `_ctx()` 래퍼 함수 ~30개가 제거됨, 회귀 테스트 통과 |
| D-018 | P1 | `1d/1w/1M` direct fetch 전환 (downsample 폐기) | done (2026-02-21) | `run_ingest_step`가 timeframe 분기 없이 direct fetch로 고정되고 downsample/lineage 코드 참조가 제거되며, 회귀 테스트(`PYENV_VERSION=coin pytest -q`)가 통과함 |
| D-019 | P1 | static 파일 self-heal + 장주기 full-fill/full-serving 정렬 | done (2026-02-21) | publish gate skip 상태에서도 canonical history 누락은 self-heal export, canonical prediction 누락은 `last_success_at` 존재 시 self-heal prediction을 수행하며, `1d/1w/1M` DB empty/state drift는 exchange earliest 기준 full-fill을 사용한다. 회귀 테스트(`PYENV_VERSION=coin pytest -q`) 통과 |
| D-020 | **P0** | 1d/1w/1M full-fill 복구 (운영 조치 + prediction 연쇄 복구) | done (2026-02-24) | 운영 조치(InfluxDB 1d/1w/1M 정리 + `ingest_state.json` cursor 제거)로 full-fill을 완료했고, 코드 레벨에서 backward coverage 재감지(`db_first vs exchange_earliest`) + detection skip override를 추가해 동일 증상의 재진입 경로를 축소했다. 검증: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py -k "rebootstrap or fullfill or D-020"` (`7 passed`) |
| D-021 | P2 | Python 상수/config 역할별 그룹화 | open | `worker_config.py` + `utils/config.py` 상수 ~55개를 역할별 섹션/dataclass로 구조화하고 재노출 패턴 제거. D-016 수행 시 함께 처리 |
| D-022 | **P0** | publish 비대칭 스케줄러 전환 (`ingest=boundary`, `publish=poll_loop 60s`) | hold (legacy reference) | `D-2026-03-04-76`(scheduler boundary hard lock) 기준으로 기본 재개 대상이 아니다. policy rollback으로 `poll_loop` 재도입이 승인된 경우에만 재평가한다. |
| D-023 | **P0** | projector decision 함수 도입(그림자 모드, 동작 불변) | hold (2026-02-24) | `D-2026-02-24-57` 해제 전까지 실행 보류. 재개 시 기존 gate 대비 diff 로그/지표를 확보한다 |
| D-024 | **P0** | publish 실행 경로 projector 전환, self-heal 분기 흡수 | hold (2026-02-24) | `D-2026-02-24-57` 해제 전까지 실행 보류. 재개 시 artifact missing이 일반 reconcile 경로에서 복구됨을 검증한다 |
| D-025 | P1 | watermark 상태파일 3종/게이트 함수 제거 | hold (2026-02-24) | `D-2026-02-24-57` 해제 전까지 실행 보류. 재개 시 `ingest/predict/export_watermarks.json` 제거와 회귀 정리를 완료한다 |
| D-026 | P1 | cross-worker 순서 레이스 회귀 테스트 고정 | hold (2026-02-24) | `D-2026-02-24-57` 해제 전까지 실행 보류. 재개 시 `publish-first / ingest-later / long TF` 자동화 테스트를 추가한다 |
| D-027 | **P0** | 직렬 pipeline 설계/가드레일 잠금 | done (2026-02-24) | `D-2026-02-24-58`로 직렬 전환 불변식(오노출 0, rollback 경계, cycle 예산, fail-closed)이 고정됐다 |
| D-028 | **P0** | runtime headroom 7일 계측 잠금 | done (2026-02-24) | `D-2026-02-24-59` scheduler-aware 계약으로 `boundary + 1h` 경로 precondition(`window >= 240`, `samples >= 240`)을 충족했고, baseline(`overrun_rate_7d_baseline=0.0`, `p95_cycle_seconds_7d_baseline=12.57`)이 `docs/PLAN_LIVING_HYBRID.md` 5.3에 기록됐다 |
| D-029 | **P0** | 직렬 실행 경로 전환(feature flag) | done (2026-02-24) | `PIPELINE_SERIAL_EXECUTION_ENABLED` 기반 직렬 전환 경로를 도입해 same-cycle publish를 검증했다. 해당 임시 flag/profile 계약은 `D-034`에서 제거됐고, 현재는 직렬 단일 경로로 고정됐다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` |
| D-030 | P1 | 직렬 경로의 상태/분기 축소 | done (2026-02-24) | serial publish 경로에서 ingest-vs-publish watermark 비교 gate 및 self-heal 분기를 비활성화하고, ingest watermark 존재 기반 reconcile로 단순화했다(`D-2026-02-24-61`). split 경로 동작은 유지된다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` |
| D-031 | P1 | 롤백 리허설 + 순서 레이스 회귀 테스트 고정 | done (2026-02-24) | split rollback 리허설 절차/증거를 `docs/PLAN_LIVING_HYBRID.md` 5.4에 고정했다. 당시 publish-only 동기화 회귀를 포함해 검증했으며, 해당 분기/테스트는 `D-033`에서 role/mode 매트릭스 삭제와 함께 retire됐다 |
| D-032 | **P0** | 삭제 전환 게이트 잠금(직렬 단일 경로 고정) | done (2026-02-24) | `D-031` 완료 + `D-028` 관측 기준(샘플 `240`, `overrun_rate=0.0`, `p95_cycle_seconds=12.57 <= 45`)으로 비열화 조건을 충족했고, rollback 경계를 split 즉시 복귀에서 배포 롤백 절차(`docs/PLAN_LIVING_HYBRID.md` 5.5)로 전환해 삭제 전제를 잠갔다 |
| D-033 | **P0** | role/mode 실행 매트릭스 삭제(`WORKER_EXECUTION_ROLE`, `WORKER_PUBLISH_MODE`) | done (2026-02-24) | `scripts/pipeline_worker.py`에서 role/mode resolver 및 stage-plan 분기(`resolve_worker_execution_role`, `resolve_worker_publish_mode`, `resolve_worker_stage_plan` 계열)를 제거하고 실행 경로를 ingest->publish 고정으로 단순화했다. publish-only state reload 경로도 제거됐고, 회귀 `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` 기준 `64 passed`를 확인했다 |
| D-034 | P1 | 직렬 플래그/legacy profile 삭제(`PIPELINE_SERIAL_EXECUTION_ENABLED`, `legacy-split`) | done (2026-02-24) | `scripts/worker_config.py`에서 `PIPELINE_SERIAL_EXECUTION_ENABLED`를 제거하고, `scripts/pipeline_worker.py`의 serial 경로를 상수 경로(`run_ingest_stage`)로 고정했다. `docker-compose.yml`에서 `legacy-split` profile/`worker-publish` 서비스를 제거해 직렬 단일 실행 경로로 잠갔다. `.env.example`/`DECISIONS`/`PLAN` 동기화 완료. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` (`64 passed`) |
| D-035 | P1 | split 전용 publish gate/self-heal 코드 삭제 | done (2026-02-24) | `_run_publish_timeframe_step`에서 split 전용 gate/self-heal 분기(`up_to_date` skip + artifact missing self-heal)를 제거하고, ingest watermark 존재 기반 단일 reconcile 경로로 고정했다. `evaluate_publish_gate_from_ingest_watermark`/`should_run_publish_from_ingest_watermark` 함수와 관련 테스트를 삭제/교체했다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` (`61 passed`) |
| D-036 | P1 | split 전용 watermark 상태파일/저장 계층 삭제 | done (2026-02-24) | `predict_watermarks.json`/`export_watermarks.json` 경로와 관련 load/save 코드를 제거했다. `WorkerPersistentState`는 `ingest_watermarks`만 유지하며, `utils/pipeline_runtime_state.py`에서 `WatermarkStore`를 삭제해 저장 계층을 `symbol_activation` 전용으로 축소했다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` (`61 passed`) |
| D-037 | P2 | 미사용 워커 엔트리포인트 제거(`worker_publish/predict/export`) | done (2026-02-24) | `scripts/worker_publish.py`, `scripts/worker_predict.py`, `scripts/worker_export.py`를 삭제하고 `scripts/worker_ingest.py` 단일 엔트리포인트로 고정했다. `.env.example`의 `WORKER_PUBLISH_MODE`와 `worker_config`의 role/mode 상수도 제거해 설정 drift를 정리했다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py` (`61 passed`) |
| D-038 | P2 | Training Snapshot Pre-Materialize (optional) | hold (2026-02-26) | 기본 경로는 on-demand extractor를 유지한다. 재개는 학습 시간/SLA 압력이 반복될 때만 허용하며, 전환 전후 비교 지표(`train_total_seconds`, `influx_query_seconds`, `failure_rate`, `peak_memory_mb`)를 고정 수집하고 SoT 정합성/원자적 스냅샷 쓰기/모델-스냅샷 버전 링크 검증을 통과해야 한다. |
| D-039 | P1 | 상태 파일 필드 인벤토리 감사(legacy/중복/파생 정리) | done (2026-03-03) | `manifest/runtime_metrics/prediction_health/symbol_activation/ingest_watermarks`에 대해 필드 단위 인벤토리(`SoT/Derived/Diagnostic/Legacy-Compat`)와 제거 후보 우선순위를 `docs/STATE_FIELD_INVENTORY.md`로 고정했다. `Keep-By-Design` 필드와 destructive cleanup 전 open question을 함께 잠금했다. |
| D-049 | P1 | CI/CD 브랜치 게이트 분리(`dev` CI-only, `main` deploy-only) | done (2026-03-04) | `.github/workflows/ci.yml`을 추가해 `main/dev` CI(test)를 분리했고, `deploy.yml`은 `main push + workflow_dispatch`로 제한했다. 로컬 스모크 경로는 `docker-compose.local.yml` override로 고정했다. |
| D-040 | **P0** | Legacy Kill Stage 1: 모델 fallback 제거 | in_progress (2026-03-05) | `workers/predict.py`에서 `model_{symbol}_{timeframe}.json`만 로드하도록 변경했고 legacy model fallback을 제거했다. canonical 누락 시 `model_missing` fail-closed 회귀(`tests/test_model_contract.py`)는 통과했으며, local compose 스모크 증거 확보 후 done으로 전환한다. |
| D-041 | **P0** | Legacy Kill Stage 2: static dual-write 제거 | in_progress (2026-03-05) | static prediction/history write/read를 canonical-only로 전환했다(`scripts/pipeline_worker.py`, `workers/predict.py`, `workers/export.py`, `utils/prediction_status.py`). 회귀: `PYENV_VERSION=coin pytest -q tests/test_model_contract.py tests/test_pipeline_worker.py tests/test_api_status.py tests/test_status_monitor.py`(100 passed), `PYENV_VERSION=coin pytest -q`(160 passed). 남은 게이트는 local compose 스모크다. |
| D-042 | P1 | Legacy Kill Stage 3: Influx legacy query fallback 제거 | in_progress (2026-03-05) | ingest(`workers/ingest.py`)와 monitor/API 공통 경로(`utils/status_consistency.py`)에서 no-timeframe legacy query fallback을 제거하고 timeframe-tag row만 신뢰하도록 고정했다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py tests/test_status_monitor.py tests/test_api_status.py`(97 passed), `PYENV_VERSION=coin pytest -q`(160 passed). 남은 게이트는 local compose 스모크다. |
| D-043 | P1 | Manifest 계약 분리(`manifest.v2` 단일 파일 내 `public`/`ops`) | in_progress (2026-03-05) | writer가 `manifest.v2`에서 `public/ops`만 출력하도록 고정했고(root `entries/summary` 제거), admin은 v2 `ops.entries`/`ops.summary`를 우선 사용하도록 잠갔다(`workers/export.py`, `admin/manifest_view.py`, `admin/app.py`). load 경로(`tests/locustfile.py`)도 v2 `public/ops` 구조 검증으로 전환했다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py tests/test_manifest_view.py`(69 passed), 전체 `pytest -q`(164 passed). 남은 게이트는 local compose 스모크다. |
| D-044 | P1 | 상태 스키마 정규화(`symbol_activation`/`prediction_health`) | in_progress (2026-03-05) | 1차로 `prediction_health`의 redundant identity(`symbol`, `timeframe`)를 제거해 key 기반 identity로 고정했다(`workers/predict.py`). 2차로 `symbol_activation`에서 `state`를 단일 SoT로 두고 `visibility/is_full_backfilled`는 state 기반 파생으로 정규화했다(`utils/pipeline_contracts.py`). 3차로 `symbol_activation` persisted payload에서 redundant field(`symbol`, `visibility`, `is_full_backfilled`)를 제거하고, manifest/admin 노출은 state 기반 파생으로 유지하도록 정렬했다(`workers/export.py`, `scripts/pipeline_worker.py`). 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py tests/test_manifest_view.py`(75 passed), `PYENV_VERSION=coin pytest -q`(170 passed). 남은 게이트는 local compose 스모크다. |
| D-045 | P2 | Orchestrator 모듈화 인터페이스 잠금 | in_progress (2026-03-05) | 1차로 `policy_eval` 경계를 `utils/serve_policy.py`에 분리하고 manifest writer가 공통 evaluator(`evaluate_serve_allowed`)를 사용하도록 전환했다(`workers/export.py`). 2차로 `ingest_watermarks` I/O를 `utils/pipeline_runtime_state.py::IngestWatermarkStore`로 분리해 orchestrator의 state file 처리 경계를 저장소 계층으로 정규화했다(`scripts/pipeline_worker.py`). 3차로 model 경로 해석 규칙을 `utils/model_store.py`로 추출해 train/predict 양쪽이 동일 `model_io` resolver를 사용하도록 잠갔다(`scripts/train_model.py`, `workers/predict.py`). 4차로 prediction health 파일 read/write를 `utils/prediction_health_store.py`로 공통화해 API/worker 중복 로직을 축소했다(`api/main.py`, `workers/predict.py`). 선행 게이트 문서(`docs/PIPELINE_REFACTOR_TARGET_SELECTION.md`, `docs/PIPELINE_REFACTOR_DESIGN_BLUEPRINT.md`)를 잠갔고 Wave A(`TS-001/002/015`) + Wave B(`TS-003/009`) + Wave C(`TS-004/005`) + Wave D 1차(`TS-010`)를 완료했다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_api_status.py tests/test_pipeline_worker.py`(84 passed), `PYENV_VERSION=coin pytest -q`(170 passed). 후속은 Wave D 2차(`TS-011`: `_ctx` wrapper 축소)와 orchestrator 호출면 슬림화(`pipeline_worker` 조합 경계 강화)다. |
| D-046 | **P0** | Status-Monitor 판정 경로 단일화(모니터 기준) | done (2026-03-04) | `/status`가 monitor와 동일한 Influx-JSON consistency override(`apply_influx_json_consistency`)를 사용하도록 정렬했다. Influx 조회 실패/결과 없음(`latest_ohlcv_ts is None`)은 JSON 판정을 그대로 유지한다. 회귀: `PYENV_VERSION=coin pytest -q tests/test_api_status.py tests/test_status_monitor.py` (`37 passed`). |
| D-047 | P1 | Scheduler mode boundary 단일화(`poll_loop` 제거) | in_progress (2026-03-05) | `WORKER_SCHEDULER_MODE`는 env 비노출 boundary 상수로 잠갔다(`scripts/worker_config.py`). `run_worker`는 boundary 이외 모드를 지원하지 않으며, invalid mode 주입(monkeypatch) 시 즉시 `ValueError`로 실패한다(`scripts/pipeline_worker.py`). 회귀: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py`(69 passed, scheduler/guard 케이스 포함), `PYENV_VERSION=coin pytest -q`(170 passed). 남은 게이트는 local compose 스모크다. |
| D-048 | P2 (Hold) | 상태 파일 축소/통합 검증(`prediction_health`/`ingest_watermarks`) | open | 축소 우선순위는 `prediction_health redundant identity -> symbol_activation redundant/derived -> 나머지`로 잠근다. `ingest_watermarks` 제거 가능성은 `ingest_state` 대체 설계+회귀 테스트로 검증하고, 인과/재시작 경계가 깨지면 파일 유지 결정을 문서로 잠근다. |
| D-050 | P1 | Operator Usecase Baseline 문서 잠금 | done (2026-03-05) | 운영자 기준 stage 계약(ingest/predict/export/serve/monitor), 실패 전파 스키마(`stage/cause/impact`), 상태 파일 축소 우선순위를 `docs/PIPELINE_OPERATOR_USECASES.md`로 고정했다. |
| D-051 | P1 | D-046 공통 판정 모듈 분리 + Docker-Ops 의존성 경계 정리 | in_progress (2026-03-05) | API/monitor 공통 판정은 `utils/status_consistency.py` 경로로 정렬돼 있고, 유즈케이스 기반 refactor 후보 매트릭스는 `docs/PIPELINE_OPERATOR_USECASES.md` 9.x에 고정했다. compose는 `monitor`가 Influx readiness 없이 기동되지 않도록 `docker-compose.yml`과 `docker-compose.local.yml` 모두 `depends_on: influxdb.condition=service_healthy`로 보강했다(`worker-ingest`는 `service_started` 유지). 로컬 override 단독 실행 시 의존 서비스 누락을 fail-fast로 노출하도록 경계를 강화했고, 병합 검증 `docker compose -f docker-compose.yml -f docker-compose.local.yml config`를 통과했다. 남은 게이트는 local compose 스모크(이미지 빌드 + fastapi import + monitor/ingest/train 최소 실행)다. |

> **Discussion Reference**: `docs/DISCUSSION_PHASE_D_AUDIT_2026-02-21.md`

## 3. Immediate Bundle (Revised 2026-03-04)
1. `D-013` — 재학습 트리거 정책 정의(1차 시간 기반)
2. `D-040` — Legacy Kill Stage 1: 모델 fallback 제거
3. `D-041` — Legacy Kill Stage 2: static dual-write 제거
4. `D-042` — Legacy Kill Stage 3: Influx legacy query fallback 제거
5. `D-043` — Manifest 계약 분리(`manifest.v2` 단일 파일 내 `public`/`ops`)
6. `D-047` — Scheduler mode boundary 단일화(`poll_loop` 제거)
7. `D-051` — D-046 공통 판정 모듈 분리 + Docker-Ops 의존성 경계 정리
8. `D-044` — 상태 스키마 정규화
9. `D-045` — Orchestrator 모듈화 인터페이스 잠금
10. `D-014` — 학습 실행 no-overlap/락 가드
11. `D-015` — 학습 실행 관측성/알림 baseline
12. `D-003` — Shadow 추론 파이프라인 도입
13. `D-004` — Champion vs Shadow 평가 리포트
14. `D-005` — 승격 게이트 정책 구현(`fail-closed`)

## 3.1 Previous Cycle KPI (Locked 2026-02-21)
1. `D-018` 완료
2. 전체 회귀 통과: `PYENV_VERSION=coin pytest -q`

## 4. Operating Rules
1. Task 시작 시 Assignee/ETA/Risk를 기록한다.
2. 완료 시 검증 증거(테스트/런타임)를 남긴다.
3. 실패/보류 시 원인과 재개 조건을 기록한다.
4. 새 부채 발견 시 `TECH_DEBT_REGISTER` 동기화가 완료 조건이다.

## 5. Archive Notes
1. Phase A 상세 원문은 `docs/archive/phase_a/*`에서 확인한다.
2. Phase B 상세 원문은 `docs/archive/phase_b/*`에서 확인한다.
3. Phase C 상세 원문은 `docs/archive/phase_c/*`에서 확인한다.
4. 활성 문서에는 현재 실행 규칙만 유지한다.

## 6. Phase C Archive Contract
1. Phase C 설계 카드/세부 Done Condition/리스크 비교표는 `docs/archive/phase_c/TASKS_MINIMUM_UNITS_PHASE_C_FULL_2026-02-20.md`를 단일 출처로 사용한다.
2. Phase C를 재개할 경우, 새 태스크 ID를 부여하고 본 문서 Active 섹션으로 다시 승격한다.
