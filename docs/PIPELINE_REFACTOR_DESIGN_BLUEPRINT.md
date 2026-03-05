# Pipeline Refactor Design Blueprint

- Last Updated: 2026-03-05
- Scope: 대규모 리팩토링 진입 전 설계 축(공통 모듈화/모듈화 편의/인터페이스화 + 추가 축) 고정
- Base: `docs/PIPELINE_OPERATOR_USECASES.md`, `docs/PIPELINE_REFACTOR_TARGET_SELECTION.md`

## 1. Design Goal
1. 목적은 "코드를 예쁘게"가 아니라 운영자 유즈케이스를 더 안전하게 구현하는 것이다.
2. 리팩토링 후에도 `fail-closed`, `last-good+degraded`, `serve_allowed` 정책은 불변이다.
3. 단계별 롤백 가능성을 유지하기 위해 big-bang이 아닌 wave 실행만 허용한다.

## 2. 공통 모듈화 가능 대상 (Requested #1)
| ID | Current Spread | Candidate | Proposed Module | Why |
|---|---|---|---|---|
| CM-01 | `pipeline_worker._prediction_health_key`, `api/main.py` key 조합 | key/path 조합 규칙 | `utils/artifact_keys.py` | identity drift 방지 |
| CM-02 | `pipeline_worker._static_export_path`, `utils/prediction_status.py`, `workers/export.py` | static artifact path 규칙 | `utils/artifact_paths.py` | canonical 경로 규칙 단일화 |
| CM-03 | `pipeline_worker._log_stage_failure_context`, `status_monitor.MonitorAlertEvent` | stage event schema | `utils/pipeline_events.py` | `stage/cause/impact` 표준화 |
| CM-04 | `pipeline_worker` runtime metrics load/aggregate/save | runtime metrics 저장/집계 | `utils/runtime_metrics_store.py` | orchestrator 책임 축소 |
| CM-05 | `workers/predict.py` + `api/main.py` health read 로직 | prediction health read/write | `utils/prediction_health_store.py` | API/worker 상태 일관성 확보 |
| CM-06 | `pipeline_worker.send_alert`, `status_monitor.send_discord_alert` | alert transport | `utils/alerting.py` | 알림 채널 교체 비용 축소 |
| CM-07 | Influx query string 조립(`workers/ingest.py`, `workers/export.py`, `utils/status_consistency.py`) | query builder | `utils/influx_queries.py` | query 계약 drift 방지 |
| CM-08 | `pipeline_worker._resolve_watermark_datetime` + store parsing | watermark parse/format | `utils/watermark_codec.py` | 상태파일 파싱 규칙 단일화 |

## 3. 모듈화하면 편리한 것들 (Requested #2)
### 3.1 Stage-oriented modularization
1. `orchestrator/preflight.py`
1. env/schema/dependency/no-overlap 검사
2. `orchestrator/stage_ingest.py`
1. ingest decision + execute + cursor commit
3. `orchestrator/stage_predict.py`
1. eligibility + predict + health transition
4. `orchestrator/stage_export.py`
1. history/prediction/manifest write + serve gate 반영
5. `orchestrator/stage_monitor.py`
1. cross-cutting event/alert emission adapter

### 3.2 Ops convenience modules
1. `ops/compose_smoke.py`
1. local smoke 명령 조합/결과 요약 자동화
2. `ops/contract_check.py`
1. manifest/public-ops schema, 상태파일 schema 검증
3. `ops/runbook_snapshot.py`
1. 장애 시 필요한 파일/로그 수집 자동화

## 4. 인터페이스화 가능한 것들 (Requested #3)
| ID | Interface | Core Methods (Draft) | Consumers |
|---|---|---|---|
| IF-01 | `StateStore` | `load_activation/save_activation`, `load_watermarks/save_watermarks`, `load_health/save_health` | worker, api, admin |
| IF-02 | `ModelStore` | `resolve_model_paths`, `load_model`, `save_model`, `load_metadata`, `save_metadata` | train, predict |
| IF-03 | `PolicyEvaluator` | `evaluate_prediction_status`, `evaluate_serve_allowed`, `apply_influx_json_consistency` | api, monitor, export |
| IF-04 | `IngestCursorResolver` | `resolve_since`, `evaluate_detection_gate`, `evaluate_rebootstrap` | worker ingest |
| IF-05 | `ArtifactPublisher` | `write_history`, `write_prediction`, `write_manifest`, `remove_symbol_exports` | worker export/predict |
| IF-06 | `AlertSink` | `emit_stage_event`, `emit_degraded`, `emit_recovery`, `emit_escalation` | worker, monitor |
| IF-07 | `Scheduler` | `init_schedule`, `resolve_due_timeframes`, `sleep_hint` | worker |

## 5. 추가 설계 축 (Beyond 1~3)
### 5.1 Env/상수 축소
1. 제거 후보:
1. `WORKER_SCHEDULER_MODE` (boundary 고정이면 env 제거)
2. primary legacy sidecar 관련 토글/설명
2. 유지 후보:
1. `TARGET_SYMBOLS`, `INGEST_TIMEFRAMES`, `ENABLE_MULTI_TIMEFRAMES`
2. `FRESHNESS_*`, `MONITOR_*`, disk watermark 계열
3. 네임스페이스 정리:
1. `TRAIN_*`, `MONITOR_*`, `SERVE_*`, `INGEST_*`로 목적 분리

### 5.2 상태파일 소유권/커밋 경계
1. `ingest_state.json`: ingest cursor hard commit owner
2. `ingest_watermarks.json`: publish 인과성 owner, cycle-end commit
3. `prediction_health.json`: degraded 전이 owner
4. `symbol_activation.json`: onboarding 노출 정책 owner
5. `runtime_metrics.json`: 운영 KPI 증거 owner

### 5.3 Fallback/legacy 정리 원칙
1. 제거 대상: silent compat fallback, dual-write 잔재, dead env fallback
2. 유지 대상: 가용성 보호 경로(`detection_unavailable_fallback_run`)는 증거 전 제거 금지
3. 문서 드리프트 정리: `CONTEXT_MIN`, `PLAN`, `SESSION_HANDOFF`의 legacy 서술 정합화

### 5.4 에러/관측 설계
1. 모든 실패 이벤트는 `stage/cause/impact`를 강제한다.
2. `cause` taxonomy를 고정한다:
1. ingest: `detection_unavailable`, `blocked_storage_guard`, `exchange_fetch_error`
2. predict: `model_missing`, `insufficient_data`, `prediction_error`
3. export: `history_write_failed`, `manifest_write_failed`
3. monitor/api/worker가 동일 taxonomy를 사용한다.

### 5.5 테스트/검증 설계
1. Contract tests:
1. interface별 consumer-driven contract test 추가
2. Negative tests:
1. canonical missing, corrupted state file, invalid env fail-fast
3. Smoke gates:
1. `worker-ingest 1 cycle`
2. `monitor 1 cycle`
3. `worker-train one-shot`
4. `fastapi import/status`

## 6. Recommended Refactor Waves
1. Wave A (문서/저위험 경계): legacy sidecar write 제거 + 문서 동기화
2. Wave B (설정/가드 강화): scheduler env 제거, unknown guard fail-open 축소
3. Wave C (State schema 축소): `symbol_activation` persisted 중복 필드 제거
4. Wave D (Interface 도입): `StateStore`, `PolicyEvaluator` 공통 reader/write path
5. Wave E (Orchestrator 슬림화): `_ctx` wrapper 축소 + stage module 분리

## 7. Do-Not-Do
1. 한 패치에서 기능 정책 변경 + 구조개편 동시 수행 금지
2. 상태파일 owner를 바꾸면서 smoke 증거 없이 merge 금지
3. 운영 경계(`serve_allowed`, `model_missing fail-closed`)를 테스트 없이 수정 금지
