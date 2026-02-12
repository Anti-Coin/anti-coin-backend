# Coin Predict Context (Minimum)

- Last Updated: 2026-02-12
- Purpose: 새 세션에서 최소 토큰으로 현재 상태를 정렬하기 위한 요약

## 1. Snapshot
1. Phase A(Reliability Baseline)는 2026-02-12에 완료했다.
2. 현재 우선 작업은 `C-005`(worker 분리), `C-006`(trigger 전환), `B-005`(endpoint sunset 정리)다.
3. 운영 현실은 Oracle Free Tier ARM + 단일 운영자다.

## 2. Non-Negotiables
1. 우선순위: Stability > Cost > Performance.
2. No silent failure, Idempotency first, UTC internally.
3. Soft stale은 경고와 함께 노출 가능, hard_stale/corrupt는 차단.

## 3. Serving Boundary
1. Source of Truth는 InfluxDB다.
2. 사용자 데이터 플레인은 SSG(static JSON)다.
3. `/status`는 운영 신호 및 프론트 경고 노출에 사용 가능하다.
4. `/history`, `/predict`는 fallback/디버그 경로이며 `B-005`에서 sunset 정리한다.

## 4. Active Decision Set
1. `D-2026-02-10-09`: InfluxDB를 SoT로 고정
2. `D-2026-02-12-13`: Phase B 전 `INGEST_TIMEFRAMES=1h` 고정
3. `D-2026-02-12-14`: SSG primary + fallback endpoint 유지
4. `D-2026-02-12-18`: prediction 저장 유지 + 실패 시 last-good + degraded
5. `D-2026-02-12-19`: `soft stale`와 `degraded` 분리
6. `D-2026-02-12-24`: soft/hard 상태 3사이클 재알림

## 5. Current Risk Focus
1. `TD-018`: API-SSG 운영 계약/endpoint sunset 최종 확정 미완료 (mitigated)
2. `TD-019`: 단일 worker 결합 구조로 인한 장애 전파 가능성
3. `TD-020`: 고정 poll loop로 인한 timeframe 확장 시 비용/정합성 리스크

## 6. Deep References
1. 현재 운영 결정: `docs/DECISIONS.md`
2. 현재 로드맵/다음 단계: `docs/PLAN_LIVING_HYBRID.md`
3. 활성 태스크 보드: `docs/TASKS_MINIMUM_UNITS.md`
4. 과거 원문 이력: `docs/archive/README.md`
