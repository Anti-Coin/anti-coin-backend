# Coin Predict Living Plan (Hybrid)

- Last Updated: 2026-02-24
- Owner: Backend/Platform
- Status: Active
- Full Phase A History: `docs/archive/phase_a/PLAN_LIVING_HYBRID_PHASE_A_FULL_2026-02-12.md`
- Full Phase B History: `docs/archive/phase_b/PLAN_LIVING_HYBRID_PHASE_B_FULL_2026-02-19.md`
- Full Phase C History: `docs/archive/phase_c/PLAN_LIVING_HYBRID_PHASE_C_FULL_2026-02-20.md`

## 1. Plan Intent
1. 이 문서는 "현재 실행 기준"만 유지한다.
2. 과거 상세 이력/원문은 Archive를 단일 출처로 사용한다.
3. 계획 변경은 실패가 아니라 리스크 제어 활동으로 취급한다.

## 2. Current State
1. Phase A(Reliability Baseline): Completed (2026-02-12)
2. Phase B(Timeframe Expansion): Completed (2026-02-19)
3. Phase C(Scale and Ops): Completed (2026-02-20)
4. Phase D(Model Evolution): Active

## 3. Fixed Invariants
1. 우선순위: Stability > Cost > Performance.
2. Source of Truth: InfluxDB.
3. 사용자 데이터 플레인: SSG(static JSON).
4. `soft stale`는 경고 허용, `hard_stale/corrupt`는 차단.
5. `soft stale`와 `degraded`는 분리 신호로 운용한다.
6. 운영 timeframe 기본값은 `1h`이며, `ENABLE_MULTI_TIMEFRAMES=true`에서만 다중 timeframe을 허용한다.

## 4. Phase Roadmap
| Phase | Status | Objective | Exit Condition |
|---|---|---|---|
| A | completed | 수집/복구/상태판정 신뢰성 확보 | A-001~A-019 완료 + Exit Criteria 충족 |
| B | completed | 다중 timeframe 전환 + 1m 비대칭 서빙 + 저장소 제약 내 운영 정합성 확보 | B-001~B-008 종료 (`B-005` sunset 완료, `B-008` sunset scope close) |
| C | completed | 장애 전파 범위 축소와 운영 관측성 강화 | C-001~C-016 완료 + 회귀/운영 smoke 근거 확보 |
| D | active | 모델 진화의 "운영 안전성" 확보(자동화 자체가 목적 아님) | D-001~D-005 핵심 게이트(인터페이스/메타데이터/shadow 비교/승격 차단) 확립 + 롤백 경로 검증 |

## 4.1 Phase C Completion Baseline
1. Phase C 시점 baseline은 `worker-ingest`/`worker-publish` 2-service였다. 현재 운영 기본은 `worker-ingest` 단일 실행 경로(ingest->publish in-cycle causal chain)로 고정됐고(`D-034`), split rollback profile은 제거됐다.
2. cadence는 `UTC boundary + detection gate` 기준으로 고정됐다.
3. monitor consistency는 `symbol+timeframe` 기준 + `PRIMARY_TIMEFRAME` legacy fallback 경계로 고정됐다.
4. stale 장기 지속 승격(`*_escalated`)과 runbook이 운영 기본 절차로 반영됐다.
5. 상세 증거/변경 이력은 `docs/archive/phase_c/*`를 단일 출처로 사용한다.
6. Phase D 전환 경로는 직렬 pipeline(`ingest -> publish` in-cycle causal chain)으로 재잠근다(`D-027`~`D-031`). `D-022`~`D-026`은 hold reference로 유지한다.

## 4.2 Phase D Model Coverage Baseline (Locked to Shared Champion)
1. 기본 커버리지는 `timeframe-shared champion` 글로벌 단일 모델로 시작하며 이를 유지한다(전 심볼 공통).
2. `symbol+timeframe dedicated` 승격/관리는 당분간 **보류(Hold)**한다. 오라클 프리 티어(ARM)의 물리적 한계(RAM)와 운영 복잡도를 고려해, 단일 모델 기반 파이프라인의 안전성부터 확보한다.
3. serving fallback 체인:
   - shared -> `insufficient_data` 차단
4. dedicated 기능은 추후 인프라가 확장 가능하거나 OOM 리스크가 완벽히 제어되었을 때만 재검토한다.
5. 관련 정책 상세는 `D-2026-02-13-32`, 구현 단위는 `D-011`에서 관리하되, `D-011`의 우선순위를 조정한다.

## 5. Next Cycle (Revised 2026-02-24)
1. `D-027` 완료: 직렬 전환 가드레일 잠금(`D-2026-02-24-58`)
2. `D-028` 완료: runtime headroom 계측 계약 잠금 + baseline 기록(`D-2026-02-24-59`)
3. `D-029` 완료: 직렬 실행 플래그 계약/코드 반영(`D-2026-02-24-60`)
4. `D-030` 완료: serial publish reconcile 경로 단순화(`D-2026-02-24-61`)
5. `D-031` 완료: 롤백 리허설 + 순서 레이스 회귀 테스트 고정
6. `D-032` 완료: 삭제 전환 게이트 잠금(직렬 단일 경로 고정)
7. `D-033` 완료: role/mode 실행 매트릭스 제거(`WORKER_EXECUTION_ROLE`, `WORKER_PUBLISH_MODE`)
8. `D-034` 완료: 직렬 플래그/legacy split profile 제거(`D-2026-02-24-63`)
9. `D-035` 완료: split 전용 publish gate/self-heal 분기 제거
10. `D-036` 완료: split 전용 watermark 상태파일/저장 계층 제거
11. `D-037` 완료: split 전용 worker 엔트리포인트 제거
12. `D-020` 완료: 1d/1w/1M full-fill 복구 + 재감지 가드 정렬(`D-2026-02-24-64`)

## 5.1 Parallel Critical Recovery (Non-Bundle)
1. `D-012`: 학습 데이터 SoT 정렬 + chunk 기반 OOM 방어
2. `D-001`: 모델 계약 명시화(`fit/predict/save/load`)
3. `D-002`: 모델 메타데이터/버전 스키마 정의

## 5.2 Previous Cycle KPI (Locked 2026-02-21)
1. `D-018` 완료
2. 전체 회귀 통과: `PYENV_VERSION=coin pytest -q`

## 5.3 D-028 Measurement Record (Before D-029)
1. Source: `static_data/runtime_metrics.json` (ingest role writer)
2. Profile: `boundary + 1h 포함` 경로 적용 (`poll_loop` 10080 샘플 경로는 비적용)
3. Runtime Evidence: `INGEST_TIMEFRAMES=1h,1d,1w,1M`
4. Runtime Evidence: `WORKER_SCHEDULER_MODE` unset (code default `boundary`)
5. Runtime Evidence: `WORKER_CYCLE_SECONDS` unset (code default `60`)
6. Runtime Evidence: `RUNTIME_METRICS_WINDOW_SIZE` unset (code default `240`)
7. Precondition(boundary profile): `RUNTIME_METRICS_WINDOW_SIZE >= 240`
8. Precondition(boundary profile): `summary.samples >= 240`
9. Metric Mapping: `p95_cycle_seconds := summary.p95_elapsed_seconds`
10. Metric Mapping: `overrun_rate := summary.overrun_rate`
11. Record `measured_at_utc`: `2026-02-24T01:01:00Z`
12. Record `window_size`: `240`
13. Record `samples`: `240`
14. Record `overrun_rate_7d_baseline`: `0.0`
15. Record `p95_cycle_seconds_7d_baseline`: `12.57`
16. Extraction Command: `jq '{measured_at_utc: .updated_at, window_size: .window_size, samples: .summary.samples, overrun_rate_7d_baseline: .summary.overrun_rate, p95_cycle_seconds_7d_baseline: .summary.p95_elapsed_seconds}' static_data/runtime_metrics.json`
17. Gate: precondition 충족 + baseline 기록 완료 (`D-029` 진입 허용)

## 5.4 D-031 Rollback Rehearsal Record
1. Purpose: split rollback 경로(당시 `PIPELINE_SERIAL_EXECUTION_ENABLED=0` + `legacy-split` profile)에서 publish-only state 동기화가 유지되는지 고정한다.
2. Fixed Regression Test: `test_reload_publish_only_shared_state_uses_file_snapshot_for_split_worker`
3. Fixed Regression Test: `test_reload_publish_only_shared_state_does_not_reload_for_ingest_worker`
4. Verification Command: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py`
5. Verification Result: `73 passed` (2026-02-24)
6. Rollback Procedure Contract: serial off: `PIPELINE_SERIAL_EXECUTION_ENABLED=0`
7. Rollback Procedure Contract: split publish worker on: `docker compose --profile legacy-split up -d worker-publish`
8. Rollback Procedure Contract: publish worker standby 해제 + cycle 시작 state reload 동작 확인

## 5.5 D-034 Serial Hard Lock Record
1. Purpose: 직렬 경로를 feature flag 없이 유일 실행 계약으로 고정한다.
2. Code Contract: `scripts/pipeline_worker.py`에서 serial 여부 결정은 `run_ingest_stage` 고정 경로만 사용한다.
3. Config Contract: `scripts/worker_config.py`에서 `PIPELINE_SERIAL_EXECUTION_ENABLED`를 제거한다.
4. Runtime Contract: `docker-compose.yml`에서 `legacy-split` profile/`worker-publish` 서비스를 제거한다.
5. Ops Contract: rollback 기본 경계는 split 즉시 복귀가 아닌 배포 롤백(runbook)만 사용한다.
6. Evidence Command: `PYENV_VERSION=coin pytest -q tests/test_pipeline_worker.py`
7. Evidence Result: `64 passed` (2026-02-24)

## 5.6 D-032 Deletion Gate Lock Record
1. Gate Objective: `D-033` 이후 split 경로 삭제를 시작하기 전에 직렬 단일 경로 전제와 rollback 경계를 고정한다.
2. Runtime Evidence Source: `D-028` 측정 기록(Section 5.3), `measured_at_utc=2026-02-24T01:01:00Z`.
3. Runtime Evidence: `summary.samples=240`, `summary.overrun_rate=0.0`, `summary.p95_elapsed_seconds=12.57`.
4. Gate Result: `p95_cycle_seconds <= 45` 조건 충족, overrun 비열화(0.0 유지)로 삭제 진입 허용.
5. Rollback Boundary Change: split 즉시 복귀(`PIPELINE_SERIAL_EXECUTION_ENABLED=0` + `legacy-split`)를 기본 계약에서 제외한다.
6. Rollback Boundary Change: 삭제 단계(`D-033+`)부터는 배포 롤백(이전 이미지/커밋 재배포)만 공식 rollback 경로로 사용한다.
7. Deployment Rollback Procedure: 운영 배포에서 직전 정상 이미지 태그로 worker 재기동한다.
8. Deployment Rollback Procedure: 배포 후 `tests/test_pipeline_worker.py` 회귀 + `/status`/manifest smoke를 수행한다.

## 6. Portfolio Capability Matrix (Current vs Next)
| Capability | Current Evidence | Next Strengthening |
|---|---|---|
| 사용자 플레인 안정 서빙(SSG) | 정적 JSON + `/status` + fallback sunset(`410`) | availability probe 자동화/리포팅 정교화 |
| 상태 정직성(fresh/stale/hard/corrupt) | API/monitor 공통 evaluator + timeframe-aware consistency | alert miss 집계 자동화 |
| 장애 신호 분리(`soft stale` vs `degraded`) | prediction health + 상태전이 알림 + escalation | 단계별 실패 시그널 세분화 |
| 수집 복구/무결성 | gap detect/refill + ingest_state/watermark 경계 | 장주기 재시작/복구 리허설 표준화 |
| 학습 실행 경계 통제 | `worker-train` one-shot + runbook | Influx SoT 학습 전환 + 재학습 트리거/락 정책 구현 |

## 7. Current Risk Register (Top)
1. `TD-012`: 자동 재학습/승격 게이트 미구현
2. `TD-010`: 모델 인터페이스 미구현
3. `TD-022`: prediction freshness 의미론(입력 stale 은닉 가능성) 정렬 필요
4. `TD-009`: dev push 즉시 배포 구조로 인한 운영 실수 영향 확대 리스크

## 8. Change Rules
1. 정책 변경은 `docs/DECISIONS.md`를 먼저 갱신한다.
2. 실행 우선순위 변경은 `docs/TASKS_MINIMUM_UNITS.md`와 동기화한다.
3. 새 기술 부채는 `docs/TECH_DEBT_REGISTER.md`에 기록한다.
4. Archive append는 Phase 종료 시점 또는 명시 요청 시 수행한다.
