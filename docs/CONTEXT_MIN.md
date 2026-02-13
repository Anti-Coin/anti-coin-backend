# Coin Predict Context (Minimum)

- Last Updated: 2026-02-13
- Purpose: 새 세션에서 최소 토큰으로 현재 상태를 정렬하기 위한 요약

## 1. Snapshot
1. Phase A(Reliability Baseline)는 2026-02-12에 완료했다.
2. 현재 우선 작업은 `B-001`(timeframe 정책 잠금), `C-002`(운영 메트릭 수집), `C-006`(경계 기반 scheduler)다.
3. `B-006`(저장소 예산 가드 + retention/downsample)은 완료되었다.
4. `1d/1w/1M`은 `1h` downsample 파생 경로로 고정되며 direct ingest는 정책상 금지다.
5. `B-005`(endpoint sunset)는 P2 트랙으로 유지한다.
6. 운영 현실은 Oracle Free Tier ARM + 단일 운영자다.

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
7. `D-2026-02-12-27`: Option A(phase-ordered stability) 기준선 채택
8. `D-2026-02-12-28`: `R-004` kickoff 계약(`B-002 -> B-003` + 검증/롤백 경계) 고정
9. `D-2026-02-13-29`: `1m` 비대칭 정책 + 저장소 가드 + `B-001` 선행 잠금 기준 채택
10. `D-2026-02-13-30`: 서빙 정책은 Hard Gate + Accuracy Signal 2층 구조 채택
11. `D-2026-02-13-31`: evaluation window/min sample/reconciliation 기준 잠금
12. `D-2026-02-13-33`: cycle cadence는 `boundary + detection gate` 하이브리드
13. `D-2026-02-13-34`: mismatch taxonomy 분리 + derived TF direct ingest 금지 경계 확정

## 5. Current Risk Focus
1. `TD-018`: API-SSG 운영 계약(필드/경로) 최종 확정 미완료
2. `TD-019`: ingest/predict/export 단일 worker 결합으로 장애 전파 리스크
3. `TD-020`: 고정 poll loop 기반 스케줄링으로 비용/정합성 리스크
4. `TD-027`: `1m` hybrid API 경계 미준수 시 오버런/계약 혼선 리스크

## 6. Deep References
1. 현재 운영 결정: `docs/DECISIONS.md`
2. 현재 로드맵/다음 단계: `docs/PLAN_LIVING_HYBRID.md`
3. 활성 태스크 보드: `docs/TASKS_MINIMUM_UNITS.md`
4. 과거 원문 이력: `docs/archive/README.md`
