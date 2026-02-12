# Coin Predict Session Handoff

- Last Updated: 2026-02-12
- Branch: `dev`

## 1. Current Snapshot
1. Phase A(Reliability Baseline) 완료.
2. 핵심 기준: 안정성 > 비용 > 성능, SSG 사용자 플레인 + InfluxDB SoT 유지.
3. `/status`는 운영/경고 신호 노출 경로로 유지, `/history`/`/predict`는 fallback 경로.
4. `R-001`~`R-004` 완료. `R-003` Option A 기준선 위에서 `R-004` kickoff 계약(`B-002 -> B-003`) 확정.
5. `B-005`는 P2 유지(조건 충족 기반 sunset, 비긴급 트랙).

## 2. Next Priority Tasks
1. `B-002`: 파일 네이밍 규칙 통일
2. `B-003`: timeframe-aware export 전환
3. `B-004`: manifest 파일 생성
4. `C-002`: 실행시간/실패율 메트릭 수집(Phase C 착수 판단 근거)
5. `R-005`: SLA-lite 지표 baseline 정의

## 3. Current Risks
1. `TD-018`: API-SSG 운영 계약(필드/경로) 최종 확정 미완료
2. `TD-019`: 단일 worker 결합 구조로 장애 전파 가능
3. `TD-020`: 고정 poll loop로 비용/정합성 리스크
4. Option A 기준으로 B 선행을 택해 단기 비용 최적화 체감(C-006)은 지연될 수 있음

## 4. R-004 Kickoff Boundary (Locked)
1. 구현 순서: `B-002` 선행, `B-003` 후행.
2. `B-002` 검증 핵심: 파일명 규칙 테스트 통과 + legacy fallback 유지 시 상태 오판 증가 없음.
3. `B-003` 검증 핵심: 다중 timeframe export 충돌 없음 + 필수 필드/`updated_at` 일관성.
4. `B-002` 롤백: legacy 우선 read로 즉시 회귀.
5. `B-003` 롤백: `1h` 단일 export 경로로 즉시 회귀.

## 5. SLA-lite Draft Metrics (for Portfolio Evidence)
1. Availability (User Plane): 측정 대상은 SSG + `/status` 경로, 계산식은 `성공 응답 수 / 전체 요청 수`.
2. Alert Miss Rate: unhealthy 상태전이(`hard_stale/corrupt/missing`) 중 알림이 누락된 비율.
3. MTTR-Stale: `hard_stale` 최초 감지 시각부터 `recovery` 감지 시각까지의 시간.
4. 현재 상태: 지표 정의/수집 경로/산출 주기 고정이 필요하며 `R-005`에서 문서화한다.

## 6. Quick Verify Commands
1. `PYENV_VERSION=coin pytest -q`
2. `python -m compileall api utils scripts tests`

## 7. Archive Guidance
1. Phase A 상세 결정/로그는 `docs/archive/phase_a/*`에서 확인한다.
2. 활성 문서에는 현재 실행 규칙만 유지한다.
