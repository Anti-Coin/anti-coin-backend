# Coin Predict Task Board (Active)

- Last Updated: 2026-02-26
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
| D-001 | P1 | 모델 계약 명시화(`fit/predict/save/load` 입출력 계약 문서화) | open | 현재 Prophet 경로의 계약이 문서/테스트로 고정됨 (추상 인터페이스가 아닌 계약 수준) |
| D-002 | P1 | 모델 메타데이터/버전 스키마 정의 | open | 버전/학습시간/데이터 범위 기록 |
| D-003 | P1 | Shadow 추론 파이프라인 도입 | open | shadow 결과 생성, 사용자 서빙 미반영. **분해 예정**(D-003a: Shadow 실행 경로, D-003b: Shadow 결과 저장, D-003c: 격리 보장) |
| D-004 | P1 | Champion vs Shadow 평가 리포트 | open | 최소 1개 지표 일별 산출 |
| D-005 | P1 | 승격 게이트 정책 구현 | open | 게이트 미달 시 승격 차단 |
| D-006 | P2 | 자동 재학습 잡(수동 트리거) | open | 운영자 수동 재학습 가능 |
| D-007 | P2 | 자동 재학습 스케줄링 | open | 설정 기반 주기 재학습 가능 |
| D-008 | P2 | 모델 롤백 절차/코드 추가 | open | 이전 champion 복귀 가능 |
| D-009 | P2 | Drift 알림 연동 | open | 임계 초과 시 경고 발송 |
| D-010 | **P0** | 장기 timeframe 최소 샘플 gate 구현 | **done (2026-02-21)** | `MIN_SAMPLE_BY_TIMEFRAME` config + `count_ohlcv_rows` query + `run_prediction_and_save` gate 삽입, 회귀 테스트 140 passed |
| D-011 | P3 (Hold) | Model Coverage Matrix + Fallback Resolver 구현 | open | (보류) Dedicated 승격 정책 대신 일단 단일 Shared 모델 서빙만 유지. `shared -> insufficient_data`만 코드/검증 |
| D-012 | **P0** | 학습 데이터 SoT 정렬 + Chunk 기반 추출 안전장치 (OOM 방지) | open | 학습 입력이 Influx SoT 기준으로 고정되고, 데이터를 한 번에 메모리에 올리지 않도록 `chunk/pagination` 기반 추출을 적용한다. 모델 추적은 MLflow `SQLite backend`로 시작하고, 학습 반영은 `symbol+timeframe partial-success` 정책을 따른다. snapshot은 `latest 1개`만 유지하며 run metadata(`run_id`, `data_range`, `row_count`, `model_version`)를 기록한다. |
| D-013 | P1 | 재학습 트리거 정책 정의(시간+이벤트) | open | 재학습 trigger matrix(시간 주기, candle 누적, 드리프트 신호)와 cooldown 정책이 문서/코드로 고정됨 |
| D-014 | P1 | 학습 실행 no-overlap/락 가드 | open | 학습 동시 실행 차단, stale lock 복구 규칙, 회귀 테스트가 고정됨 |
| D-015 | P2 | 학습 실행 관측성/알림 baseline | open | 학습 실행시간/성공-실패/최근성 메트릭과 장애 알림 기준이 운영 문서와 함께 반영됨 |
| D-016 | P2 | `pipeline_worker.py` 상태 관리 분리(`worker_state.py`) | open | watermark/prediction_health/symbol_activation/runtime_metrics load/save/upsert가 `scripts/worker_state.py`로 이동, 회귀 테스트 통과 |
| D-017 | P2 | `pipeline_worker.py` `_ctx()` 래퍼 패턴 해소 | open | 테스트가 `workers.*` 직접 참조로 전환되고 `_ctx()` 래퍼 함수 ~30개가 제거됨, 회귀 테스트 통과 |
| D-018 | P1 | `1d/1w/1M` direct fetch 전환 (downsample 폐기) | done (2026-02-21) | `run_ingest_step`가 timeframe 분기 없이 direct fetch로 고정되고 downsample/lineage 코드 참조가 제거되며, 회귀 테스트(`PYENV_VERSION=coin pytest -q`)가 통과함 |
| D-019 | P1 | static 파일 self-heal + 장주기 full-fill/full-serving 정렬 | done (2026-02-21) | publish gate skip 상태에서도 canonical history 누락은 self-heal export, canonical prediction 누락은 `last_success_at` 존재 시 self-heal prediction을 수행하며, `1d/1w/1M` DB empty/state drift는 exchange earliest 기준 full-fill을 사용한다. 회귀 테스트(`PYENV_VERSION=coin pytest -q`) 통과 |
| D-020 | **P0** | 1d/1w/1M full-fill 복구 (운영 조치 + prediction 연쇄 복구) | done (2026-02-24) | 운영 조치(InfluxDB 1d/1w/1M 정리 + `ingest_state.json` cursor 제거)로 full-fill을 완료했고, 코드 레벨에서 backward coverage 재감지(`db_first vs exchange_earliest`) + detection skip override를 추가해 동일 증상의 재진입 경로를 축소했다. 검증: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py -k "rebootstrap or fullfill or D-020"` (`7 passed`) |
| D-021 | P2 | Python 상수/config 역할별 그룹화 | open | `worker_config.py` + `utils/config.py` 상수 ~55개를 역할별 섹션/dataclass로 구조화하고 재노출 패턴 제거. D-016 수행 시 함께 처리 |
| D-022 | **P0** | publish 비대칭 스케줄러 전환 (`ingest=boundary`, `publish=poll_loop 60s`) | hold (2026-02-24) | `D-2026-02-24-57` 해제 전까지 실행 보류. 재개 시 long TF publish lag p95 <= 1m 및 overrun 비열화를 검증한다 |
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

> **Discussion Reference**: `docs/DISCUSSION_PHASE_D_AUDIT_2026-02-21.md`

## 3. Immediate Bundle (Revised 2026-02-26)
1. `D-012` — 학습 데이터 SoT 정렬 + Chunk 기반 OOM 방어 + SQLite tracking/partial-success/snapshot latest-only 정책 잠금
2. `D-001` — 모델 계약 명시화
3. `D-002` — 메타데이터/버전 스키마

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
