# Coin Predict Context (Minimum)

- Last Updated: 2026-02-13
- Purpose: 새 세션에서 최소 토큰으로 현재 상태를 정렬하기 위한 요약

## 1. Snapshot
1. Phase A(Reliability Baseline)는 2026-02-12에 완료했다.
2. 현재 우선 작업은 `B-001`(timeframe 정책 잠금), `B-002`(파일 네이밍), `B-003`(timeframe-aware export)다.
3. `B-006`(저장소 예산 가드 + retention/downsample)은 B 선행 트랙으로 추가됐다.
4. `C-005`, `C-006`는 `B-003` 검증 증거 확보 전까지 gated 상태다.
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

## 5. Current Risk Focus
1. `TD-027`: `1m` 예측/서빙 경계 불명확으로 인한 오버런/계약 혼선 리스크
2. `TD-028`: Free Tier 50GB 제약에서 `1m` 장기 보관 시 디스크 고갈 리스크
3. `TD-029`: downsample lineage/검증 기준 미정으로 인한 정합성 리스크

## 6. Deep References
1. 현재 운영 결정: `docs/DECISIONS.md`
2. 현재 로드맵/다음 단계: `docs/PLAN_LIVING_HYBRID.md`
3. 활성 태스크 보드: `docs/TASKS_MINIMUM_UNITS.md`
4. 과거 원문 이력: `docs/archive/README.md`
