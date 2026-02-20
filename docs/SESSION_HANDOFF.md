# Coin Predict Session Handoff

- Last Updated: 2026-02-20
- Branch: `dev`

## 1. Current Snapshot
1. Phase A 완료(2026-02-12), Phase B 완료(2026-02-19).
2. 핵심 기준: 안정성 > 비용 > 성능, SSG 사용자 플레인 + InfluxDB SoT 유지.
3. `/status`는 운영 신호 경로, `/history`/`/predict`는 sunset tombstone(`410`).
4. `R-005` 완료: SLA-lite baseline(availability/alert miss/MTTR) 고정.
5. `B-005` 완료: endpoint sunset 코드/테스트 반영 + 오너 확인 기반 fallback 비의존 운영 검증.
6. `B-007` 완료: admin manifest-first 대시보드 확장 + 회귀 검증.
7. `B-008` 완료(`sunset scope close`): FE 미구축 상태에서 종료, FE 재개 시 재오픈.
8. Phase B 상세 원문은 `docs/archive/phase_b/*`로 이동했다.
9. `C-010` 완료: ingest_state(즉시) vs ingest watermark(사이클 종료 커밋) 경계를 helper로 분리했고 characterization test를 추가했다.
10. `C-001` 완료(2026-02-20): `TARGET_SYMBOLS` 정규화/형식 검증/중복 제거 + canary 추가 검증 테스트를 고정했다.
11. `C-003` 완료(2026-02-20): `tests/locustfile.py`를 static + `/status` 중심 baseline/stress 시나리오로 갱신했다.
12. `C-012` 완료(2026-02-20): 재배치 전제 계약 문서(`docs/C-012_RELOCATION_CONTRACT_PLAN.md`)에 compose/Docker/import 계약 맵 + 단계별 검증/롤백 runbook을 잠금했다.
13. `C-016` 완료(2026-02-20): monitor 장기 지속 상태 escalation(`*_escalated`) + runbook(`docs/RUNBOOK_STALE_ESCALATION.md`) + 회귀 테스트를 고정했다.
14. `C-013` 완료(2026-02-20): `pipeline_worker`에서 ingest detection gate/underfill 판단을 helper 2개로 분리해 동작 불변 가독성 개선을 적용했다(timeboxed micro-refactor).
15. `C-004` 완료(2026-02-20): `worker-train` one-shot 서비스(`ops-train` profile)와 `train_model` CLI 인자(`--symbols/--timeframes/--lookback-limit`)를 고정했고, 실행/복구 절차를 `docs/RUNBOOK_TRAIN_JOB.md`로 명문화했다.
16. 완료 증거: `PYENV_VERSION=coin pytest -q` 통과(`137 passed`, 2026-02-20) + 운영 smoke 확인.

## 2. Phase C Detailed Runtime Baseline
1. cadence: `UTC boundary + detection gate`를 기본 실행 규칙으로 유지한다.
2. worker topology: `worker-ingest`/`worker-publish` 2-service를 운영 기본으로 유지한다.
3. publish trigger: ingest watermark advance 기반 gate를 유지한다.
4. consistency: monitor Influx latest는 `symbol+timeframe` 기준으로 조회한다.
5. orchestrator 변경(`C-010`)은 동작 불변(behavior-preserving)을 강제한다.

## 3. Next Priority Tasks
1. `D-001`: 모델 인터페이스 계약(`fit/predict/save/load`) 고정
   - Done 기준: 기존 Prophet 경로 호환 + 계약 테스트 가능 기준선 확정
2. `D-002`: 모델 메타데이터/버전 스키마 정의
   - Done 기준: 모델 버전/학습시각/학습 데이터 범위 메타데이터를 일관된 스키마로 기록

## 3.1 Stale RCA Follow-up (Taskized)
1. `C-014`(P1): done (2026-02-20), derived TF `already_materialized` skip 시 ingest watermark를 DB latest로 동기화해 publish catch-up starvation 완화
2. `C-015`(P1): done (2026-02-20), prediction status legacy fallback을 `PRIMARY_TIMEFRAME` 전용으로 제한해 non-primary timeframe 판정 오염 차단
3. `C-016`(P2): done (2026-02-20), monitor escalation 이벤트(`*_escalated`)와 운영 runbook을 고정

## 4. Phase D Detailed Baseline
1. coverage 기본값은 `timeframe-shared champion`이다.
2. dedicated는 승격 조건(최소 샘플/성능 개선/비용 허용) 충족 시에만 도입한다.
3. fallback 체인은 `dedicated -> shared -> insufficient_data`로 고정한다.
4. dedicated 실패 은닉(조용한 shared 대체)은 금지한다.
5. 선행 태스크 묶음은 `D-001`/`D-002`/`D-003`/`D-004`/`D-005`다.

## 5. Current Risks
1. `TD-020`: 스케줄링/실행 비용 및 정합성 리스크
2. `TD-024`: 단계별 부분 실패 알림 세분화 미완료
3. `TD-027`: `1m` hybrid 경계 재활성화 시 정책/구현 재정렬 필요
4. `TD-009`: dev push 즉시 배포 구조 리스크

## 6. Runtime Notes
1. 로컬 `.env`는 참고용이며, 실제 서버 런타임은 `.env.prod` 기준 주입이다.
2. sunset 이후 운영 기본 점검은 `/status` + static 산출물 확인 경로를 사용한다.

## 7. Quick Verify Commands
1. `PYENV_VERSION=coin pytest -q`
2. `python -m compileall api utils scripts tests`
3. `PYENV_VERSION=coin locust -f tests/locustfile.py --tags baseline --headless -u 10 -r 2 -t 3m --host http://localhost`
4. `PYENV_VERSION=coin locust -f tests/locustfile.py --tags stress --headless -u 30 -r 5 -t 3m --host http://localhost`

## 8. Archive Guidance
1. Phase A 상세 이력: `docs/archive/phase_a/*`
2. Phase B 상세 이력: `docs/archive/phase_b/*`
3. 활성 문서는 현재 실행 기준만 유지한다.
