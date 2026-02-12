# Coin Predict Living Plan (Hybrid)

- Last Updated: 2026-02-12
- Owner: Backend/Platform
- Status: Active
- Full Phase A History: `docs/archive/phase_a/PLAN_LIVING_HYBRID_PHASE_A_FULL_2026-02-12.md`

## 1. Plan Intent
1. 이 문서는 "현재 실행 기준"만 유지한다.
2. 과거 진행 로그와 상세 회고는 Archive에서 관리한다.
3. 계획 변경은 실패가 아니라 리스크 제어 활동으로 취급한다.

## 2. Current State
1. Phase A(Reliability Baseline): Completed (2026-02-12)
2. Phase B(Timeframe Expansion): Ready
3. Phase C(Scale and Ops): Ready
4. Phase D(Model Evolution): Backlog

## 3. Fixed Invariants
1. 우선순위: Stability > Cost > Performance.
2. Source of Truth: InfluxDB.
3. 사용자 데이터 플레인: SSG(static JSON).
4. `soft stale`는 경고 허용, `hard_stale/corrupt`는 차단.
5. `soft stale`와 `degraded`는 분리 신호로 운용.
6. Phase B 전 운영 timeframe은 `1h` 고정.

## 4. Phase Roadmap
| Phase | Status | Objective | Exit Condition |
|---|---|---|---|
| A | completed | 수집/복구/상태판정 신뢰성 확보 | A-001~A-019 완료 + Exit Criteria 충족 |
| B | ready | 다중 timeframe 구조 전환 | timeframe-aware export + manifest + 정책 분리 |
| C | ready | worker 분리/운영 관측성 강화 | C-005/C-006 완료 후 안정 운용 증거 확보 |
| D | backlog | 모델 진화 자동화 | champion/shadow 비교 + 승격/롤백 게이트 확립 |

## 5. Next Cycle (Recommended)
1. `C-005`: pipeline worker 역할 분리(ingest/predict/export)
2. `C-006`: timeframe 경계/새 캔들 감지 기반 trigger 전환
3. `B-005`: `/history`/`/predict` sunset 정리

## 6. Current Risk Register (Top)
1. `TD-018`: API-SSG 운영 계약 최종 확정 전까지 경계 혼선 가능
2. `TD-019`: 단일 worker 결합으로 장애 전파 가능
3. `TD-020`: 고정 poll loop로 비용/정합성 리스크
4. `TD-024`: 단계별 부분 실패 알림 세분화 미완료

## 7. Change Rules
1. 정책 변경은 `docs/DECISIONS.md`를 먼저 갱신한다.
2. 실행 우선순위 변경은 `docs/TASKS_MINIMUM_UNITS.md`와 동기화한다.
3. 새 기술 부채는 `docs/TECH_DEBT_REGISTER.md`에 기록한다.
4. 상세 진행 로그는 Archive에 append한다.
