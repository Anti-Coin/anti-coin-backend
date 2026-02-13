# Coin Predict Session Handoff

- Last Updated: 2026-02-13
- Branch: `dev`

## 1. Current Snapshot
1. Phase A(Reliability Baseline) 완료.
2. 핵심 기준: 안정성 > 비용 > 성능, SSG 사용자 플레인 + InfluxDB SoT 유지.
3. `/status`는 운영/경고 신호 노출 경로로 유지, `/history`/`/predict`는 fallback 경로.
4. `R-001`~`R-004` 완료. `D-2026-02-13-29/30/31/32/33/34` 반영으로 Phase B/C/D 기준선을 보정.
5. `B-002` 완료: canonical `{symbol}_{timeframe}` 네이밍 적용 + legacy 호환(dual-write) 유지 + 회귀 테스트 `29 passed`.
6. `B-005`는 P2 유지(조건 충족 기반 sunset, 비긴급 트랙).
7. `B-003` 완료: 다중 timeframe(`1h/1d/1w/1M`) + 5 symbol 조합에서 실운영 cycle 확인(약 30초), `1m` prediction 비생성 정책 반영.
8. config gate 변경: `ENABLE_MULTI_TIMEFRAMES`(default `0`) 도입. 기본은 `1h` 고정 유지, 명시 활성화 시 다중 timeframe 허용.
9. `B-004` 완료: worker cycle마다 `manifest.json` 생성(심볼/타임프레임 상태 요약 + degraded/freshness 병합).
10. `B-006` 완료: `1m` retention(`14d default / 30d cap`) + disk watermark(70/85/90) + `1h->1d/1w/1M` downsample/lineage(`downsample_lineage.json`) 경로 반영, 회귀 `76 passed`.
11. `D-2026-02-13-34` 반영: reconciliation mismatch semantics를 `internal_deterministic_mismatch`/`external_reconciliation_mismatch`로 분리하고, `1d/1w/1M` direct ingest 금지 경계를 정책으로 고정.

## 2. Next Priority Tasks
1. `B-001`: timeframe tier 정책 매트릭스 잠금(1m 비대칭 + `latest closed 180` + `14d/30d` + Hard Gate+Accuracy + mismatch taxonomy + derived TF direct ingest 금지 경계)
2. `C-002`: 실행시간/실패율/overrun/missed boundary 메트릭 수집
3. `C-006 -> C-007`: boundary scheduler + detection gate 하이브리드 전환
4. `B-007`: admin/app.py timeframe 운영 대시보드 확장
5. `B-005`: `/history`/`/predict` sunset 조건 충족 여부 재검증

## 3. Current Risks
1. `TD-018`: API-SSG 운영 계약(필드/경로) 최종 확정 미완료
2. `TD-027`: `1m` hybrid API 경계(`latest closed 180`) 미준수 시 오버런/계약 혼선
3. `TD-019`: ingest/predict/export 단일 worker 결합으로 장애 전파 리스크
4. `TD-020`: 고정 poll loop 기반 스케줄링으로 비용/정합성 리스크

## 4. R-004 Kickoff Boundary (Locked)
1. `B-001` 정책 잠금이 선행되지 않으면 `B-002`/`B-003` 착수는 보류한다.
2. 구현 순서: `B-001` 잠금 후 `B-002` 선행, `B-003` 후행.
3. `B-002` 검증 핵심: 파일명 규칙 테스트 통과 + legacy fallback 유지 시 상태 오판 증가 없음.
4. `B-003` 검증 핵심: 다중 timeframe export 충돌 없음 + 필수 필드/`updated_at` 일관성 + `1m` prediction 비생성.
5. `B-002` 롤백: legacy 우선 read로 즉시 회귀.
6. `B-003` 롤백: `1h` 단일 export 경로로 즉시 회귀.

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
