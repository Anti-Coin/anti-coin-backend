# Coin Predict Living Plan (Hybrid)

- Last Updated: 2026-02-21
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
1. worker topology는 `worker-ingest`/`worker-publish` 2-service로 고정됐다.
2. cadence는 `UTC boundary + detection gate` 기준으로 고정됐다.
3. monitor consistency는 `symbol+timeframe` 기준 + `PRIMARY_TIMEFRAME` legacy fallback 경계로 고정됐다.
4. stale 장기 지속 승격(`*_escalated`)과 runbook이 운영 기본 절차로 반영됐다.
5. 상세 증거/변경 이력은 `docs/archive/phase_c/*`를 단일 출처로 사용한다.

## 4.2 Phase D Model Coverage Baseline (Locked to Shared Champion)
1. 기본 커버리지는 `timeframe-shared champion` 글로벌 단일 모델로 시작하며 이를 유지한다(전 심볼 공통).
2. `symbol+timeframe dedicated` 승격/관리는 당분간 **보류(Hold)**한다. 오라클 프리 티어(ARM)의 물리적 한계(RAM)와 운영 복잡도를 고려해, 단일 모델 기반 파이프라인의 안전성부터 확보한다.
3. serving fallback 체인:
   - shared -> `insufficient_data` 차단
4. dedicated 기능은 추후 인프라가 확장 가능하거나 OOM 리스크가 완벽히 제어되었을 때만 재검토한다.
5. 관련 정책 상세는 `D-2026-02-13-32`, 구현 단위는 `D-011`에서 관리하되, `D-011`의 우선순위를 조정한다.

## 5. Next Cycle (Recommended)
1. `D-018` 완료(2026-02-21): `1d/1w/1M` direct fetch 전환(downsample 폐기)
2. `D-012` 수행: 학습 데이터 SoT 정렬(Influx 기반 closed-candle snapshot + chunk 기반 OOM 방어 추출)
3. `D-001` 수행: 모델 계약 명시화(`fit/predict/save/load`, 추상 인터페이스 도입은 보류)
4. `D-002` 수행: 모델 메타데이터/버전 스키마 정의

## 5.1 Cycle KPI (Locked 2026-02-21)
1. `D-018` 완료
2. `D-012` 완료
3. 전체 회귀 통과: `PYENV_VERSION=coin pytest -q`

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
3. `TD-030`: 장기 TF 샘플 부족 차단/품질표시 미구현
4. `TD-009`: dev push 즉시 배포 구조로 인한 운영 실수 영향 확대 리스크

## 8. Change Rules
1. 정책 변경은 `docs/DECISIONS.md`를 먼저 갱신한다.
2. 실행 우선순위 변경은 `docs/TASKS_MINIMUM_UNITS.md`와 동기화한다.
3. 새 기술 부채는 `docs/TECH_DEBT_REGISTER.md`에 기록한다.
4. Archive append는 Phase 종료 시점 또는 명시 요청 시 수행한다.
