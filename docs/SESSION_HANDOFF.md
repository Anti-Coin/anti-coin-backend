# Coin Predict Session Handoff

- Last Updated: 2026-02-19
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
12. `I-2026-02-13-01` 반영: `1h` canonical underfill 탐지 시 lookback 재부트스트랩 강제(`state/db cursor drift` 복구), 회귀 `83 passed`.
13. `D-2026-02-13-35` 반영: 위 `I-2026-02-13-01`은 임시 방편(containment)이며 RCA 완료 전 최종 해결로 간주하지 않음.
14. `B-001` 완료 (2026-02-17): worker full-first bootstrap(`exchange earliest`) + symbol activation(`registered/backfilling/ready_for_serving`) + manifest `visibility/is_full_backfilled/coverage_*` 반영, hidden 심볼 `serve_allowed=false`, 회귀 `87 passed`.
15. FE 통합은 백엔드 우선 원칙으로 defer: FE가 `manifest.visibility=hidden_backfilling`를 소비해 심볼 비노출하는 작업은 신규 `B-008(P2)`로 등록.
16. `C-008` 시작 (2026-02-17): `1h underfill` RCA 착수(temporary guard `I-2026-02-13-01`의 sunset/유지 결론 도출)
17. `C-008` 완료 (2026-02-17): legacy fallback 오염 경로 차단(`not exists r["timeframe"]`) + 회귀 `89 passed` + `D-2026-02-17-37` 반영. guard 7일 관찰은 운영 병행 메모로 전환.
18. `C-005` 확장 완료 (2026-02-17): 엔트리포인트 분리(`worker_ingest.py`, `worker_predict.py`, `worker_export.py`, `worker_publish.py`) + `worker-ingest`/`worker-publish` 2-service 전환 + ingest watermark 기반 publish gate(`ingest/predict/export watermarks`) 적용, 회귀 `106 passed`.
19. `C-005` 코드 구조 정리 완료 (2026-02-17): domain 로직을 `workers/ingest.py`, `workers/predict.py`, `workers/export.py`로 분리하고 `scripts/pipeline_worker.py`를 orchestrator/runtime glue 래퍼 중심으로 정리, 회귀 `106 passed`.
20. `D-2026-02-19-39` 반영: multi-timeframe freshness 기본 임계값을 확장(`1w` soft/hard=`8d/16d`, `1M` soft/hard=`35d/70d`)하고 `4h`는 legacy compatibility 경로로 유지.
21. freshness 임계값 설정 동기화: `utils/config.py`, `.env.example`, `docs/DECISIONS.md`, `docs/TASKS_MINIMUM_UNITS.md`, `docs/CONTEXT_MIN.md` 반영 + 회귀 `106 passed`.
22. `C-009` 완료 (2026-02-19): monitor Influx-JSON consistency를 `symbol+timeframe` 기준으로 보강하고 `PRIMARY_TIMEFRAME` legacy fallback을 유지, 관련 회귀 테스트 추가 포함 전체 `108 passed`.
23. `D-2026-02-19-40` 반영: monitor 대사 기준을 timeframe-aware로 고정.

## 2. Next Priority Tasks
1. `R-005`: SLA-lite 지표 baseline(공식/데이터 소스/산출 주기) 확정
2. `B-007`: admin/app.py timeframe 운영 대시보드 확장
3. `B-005`: `/history`/`/predict` sunset 조건 충족 여부 재검증
4. `B-008`(P2): FE 심볼 노출 게이트 연동(`hidden_backfilling` 필터)

## 2.1 Runtime Note
1. 로컬 `.env`는 참고용이며, 실제 서버 런타임 환경 변수는 `.env.prod` 기준으로 주입된다.
2. `C-008` 후속 메모: guard(`I-2026-02-13-01`) 재트리거/재백필 비용은 7일간 개발 병행 관찰로 기록하고, 차기 판단 근거는 `C-002` runtime evidence에 누적한다.

## 3. Current Risks
1. `TD-018`: API-SSG 운영 계약(필드/경로) 최종 확정 미완료
2. `TD-027`: `1m` hybrid API 경계(`latest closed 180`) 미준수 시 오버런/계약 혼선
3. `TD-019`: 단일 worker 결합 리스크는 2-service 분리로 완화됐으나, publish 내부 predict/export 완전 분리는 미적용
4. `TD-020`: 고정 poll loop 기반 스케줄링으로 비용/정합성 리스크
5. `1h` underfill guard가 임시 방편으로 장기 고착될 경우, 근본 원인 은닉/불필요 재백필 비용 리스크
6. monitor 대사 기준이 timeframe을 분리하지 않으면 multi-timeframe에서 hard_stale 오탐/누락 리스크

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
