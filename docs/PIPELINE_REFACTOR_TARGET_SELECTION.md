# Pipeline Refactor Target Selection (Usecase Gate)

- Last Updated: 2026-03-05
- Status: Locked for pre-refactor gate
- Purpose: 대규모 리팩토링 진입 전, `PIPELINE_OPERATOR_USECASES` 기준으로 제거/축소/유지 대상을 먼저 확정한다.

## 1. Selection Rules
1. 기준 문서는 `docs/PIPELINE_OPERATOR_USECASES.md`를 단일 출처로 사용한다.
2. 우선순위는 `Stability > Cost > Performance`를 고정한다.
3. `serve_allowed`, `ingest_watermarks`, `prediction_health` 핵심 필드는 증거 없이 제거하지 않는다.
4. fallback 축소는 "침묵 실패 증가 여부"를 먼저 검증한다.
5. 각 항목은 `Decision + Why + Verify + Rollback` 4요소가 없으면 실행 금지다.

## 2. Scope Snapshot (Current)
1. Legacy kill 1~3(`model/static/influx fallback`)은 코드 반영 완료, local compose smoke 증거는 잔여다.
2. `D-045` 모듈화는 `policy_eval/state_store/model_io` 1차 분리까지 반영됐다.
3. 다음 대규모 리팩토링은 본 문서의 `REMOVE_NEXT`/`REDUCE_NEXT` 승인 후에만 진입한다.

## 3. Target Matrix
| ID | Domain | Target | Decision | Why (Usecase) | Verify | Rollback |
|---|---|---|---|---|---|---|
| TS-001 | Model IO | `scripts/train_model.py` primary legacy model write(`model_{symbol}.json`) | DONE (2026-03-05) | UC-PRED-01은 canonical 누락 fail-closed를 요구한다. runtime read가 canonical-only면 sidecar legacy write는 계약 노이즈다. | `tests/test_train_model.py`, `tests/test_model_contract.py`, `pytest -q` 통과 | 커밋 단위 revert |
| TS-002 | Model IO | `scripts/train_model.py` primary legacy metadata write(`model_{symbol}.meta.json`) | DONE (2026-03-05) | TS-001과 동일. metadata도 canonical 단일 계약으로 맞춰 drift를 줄인다. | `tests/test_train_model.py`, `pytest -q` 통과 | 커밋 단위 revert |
| TS-003 | Scheduler Config | `WORKER_SCHEDULER_MODE` env 노출(`scripts/worker_config.py`) | DONE (2026-03-05) | UC-OPS-01은 misconfig fail-fast를 요구한다. boundary 단일 정책에서 env 표면을 제거해 오설정 입력면을 축소한다. | `tests/test_pipeline_worker.py::test_worker_scheduler_mode_env_is_ignored`, `tests/test_pipeline_worker.py`(69 passed), `pytest -q`(170 passed) | 커밋 단위 revert |
| TS-004 | State Store | `symbol_activation` persisted redundant field `symbol` | DONE (2026-03-05) | key가 identity이므로 중복 필드는 drift 위험만 만든다. | `tests/test_pipeline_worker.py::test_symbol_activation_store_persists_state_only_fields`, `tests/test_pipeline_worker.py`(69 passed), `pytest -q`(170 passed) | 커밋 단위 revert |
| TS-005 | State Store | `symbol_activation` persisted `visibility/is_full_backfilled` | DONE (2026-03-05) | `state` 단일 SoT 정책(D-044 2차)과 중복. persisted 파생 제거 후보다. | `tests/test_pipeline_worker.py::test_build_runtime_manifest_marks_hidden_symbol_unservable`, `tests/test_manifest_view.py`, `pytest -q`(170 passed) | 커밋 단위 revert |
| TS-006 | State Store | `ingest_watermarks.json` 파일 자체 | KEEP | UC-ING-02/03, Stage 7 serve gate 인과 경계의 핵심이다. 대체 증거 전 제거 금지. | 기존 회귀 + restart/reconcile smoke | N/A |
| TS-007 | State Store | `prediction_health` core fields(`degraded`, `last_*`, `consecutive_failures`, `last_error`) | KEEP | UC-PRED-03 last-good+degraded 정책의 owner다. | `/status` + monitor 회귀 | N/A |
| TS-008 | Runtime Metrics | `runtime_metrics.recent_cycles` window upper bound | REDUCE_NEXT | 파일 보존 비용 최적화 후보. 운영자 관측성을 유지한 채 window 상한만 잠그는 축소다. | runtime metrics 회귀 + 7일 KPI 추출 가능성 확인 | 상한값 되돌림 |
| TS-009 | Guard | `scripts/worker_guards.py::coerce_storage_guard_level` unknown level -> normal fallback | DONE (2026-03-05) | unknown을 normal로 내리면 fail-open 성향이다. unknown은 `block`으로 강등해 보수 경계로 잠근다. | `tests/test_pipeline_worker.py::test_coerce_storage_guard_level_unknown_falls_back_to_block`, `tests/test_pipeline_worker.py`(69 passed), `pytest -q`(170 passed) | 커밋 단위 revert |
| TS-010 | API/Ops Interface | `api/main.py` 내 prediction health read 로직 중복 | DONE (2026-03-05) | `StateStore` 인터페이스 후보. UC-MON-01/UC-PRED-03 상태 일관성 유지 위해 공통 reader 필요. | `tests/test_api_status.py`, `tests/test_pipeline_worker.py`(84 passed), `pytest -q`(170 passed) | 커밋 단위 revert |
| TS-011 | Orchestrator | `_ctx()` 기반 monkeypatch 호환 래퍼 군 | IN_PROGRESS (2026-03-05) | `D-017` 목표. 조합 책임만 남기기 위해 wrapper 축소 필요. 단, 테스트 계약 동시 이관이 선행 조건이다. dead wrapper(`_load/_save_prediction_health`, `_static_export_candidates`, `_extract_updated_at_from_files`) 제거를 완료했다. | `tests/test_pipeline_worker.py`, `tests/test_manifest_view.py`, `tests/test_api_status.py`(90 passed), `pytest -q`(170 passed) | 단계 커밋 revert |
| TS-012 | Env Simplification | `PREDICTION_DISABLED_TIMEFRAMES` env | DEFER | 현재 1m 정책이지만 도메인 정책 변경 가능성(비용 대비 위험 낮음). 즉시 제거 우선순위는 낮다. | 정책 확정 후 테스트 재잠금 | N/A |
| TS-013 | Runtime Metrics | `runtime_metrics.json` 파일 자체 | DEFER | D-028/운영 KPI 근거 파일. external metrics backend 없으면 제거 불가. | 대체 경로 설계 후 재평가 | N/A |
| TS-014 | Ingest Logic | `detection_unavailable_fallback_run` 경로 | KEEP | 거래소 detection 일시 실패 시 ingest 진행은 가용성 보호 장치다. 제거 시 missed ingest 리스크가 커진다. | detection unavailable 회귀(`test_pipeline_worker.py`) 유지 | N/A |
| TS-015 | Docs Contract | `CONTEXT_MIN/PLAN/SESSION_HANDOFF`의 legacy fallback 서술 | DONE (2026-03-05) | 코드 계약과 문서 계약이 어긋나면 잘못된 의사결정을 유도한다. | `CONTEXT_MIN/PLAN/SESSION_HANDOFF/MODEL_CONTRACT/DECISIONS/RUNBOOK_TRAIN_JOB` 동기화 diff review | 커밋 단위 revert |
| TS-016 | Compose Ops | local override 단독 실행 허용 경로 | KEEP (Fail-Fast) | UC-OPS-01. 현재 `depends_on` 강화로 의존 누락을 fail-fast로 노출하는 방향이 맞다. | `docker compose -f docker-compose.yml -f docker-compose.local.yml config` + local smoke | N/A |

## 4. Execution Gate (Before Big Refactor)
1. `REMOVE_NEXT`/`REDUCE_NEXT` 중 실행할 항목 ID를 먼저 고른다(최대 2~3개/웨이브).
2. 각 웨이브는 기능 변경과 구조 변경을 분리한다.
3. 웨이브마다 `pytest + local compose smoke` 증거를 확보하고 다음 웨이브로 이동한다.

## 5. Proposed Wave Order
1. Wave A (Low blast radius): TS-001, TS-002, TS-015 (**completed 2026-03-05**)
2. Wave B (Config/Guard tightening): TS-003, TS-009 (**completed 2026-03-05**)
3. Wave C (State schema tightening): TS-004, TS-005 (**completed 2026-03-05**)
4. Wave D (Orchestrator surface reduction): TS-010 (**completed 2026-03-05**), TS-011 (**in progress 2026-03-05**)
5. Deferred set: TS-012, TS-013 (정책/인프라 조건 충족 시 재개)

## 6. Open Questions (Need Owner Confirmation)
1. TS-001/002 실행 시, primary legacy model/meta sidecar를 즉시 중단해도 운영 런북 호환성 문제가 없는가?
2. TS-003 질문은 해소됐다. 현재 scheduler 경계는 env 비노출 `boundary` 단일값으로 잠금했다.
3. TS-005 질문은 해소됐다. manifest/admin 노출은 `state` 기반 파생(`visibility/is_full_backfilled`)으로 유지한다.
