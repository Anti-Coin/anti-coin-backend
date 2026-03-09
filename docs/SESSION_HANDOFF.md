# Coin Predict Session Handoff

- Last Updated: 2026-03-09
- Branch: `task/d046-status-monitor-parity`

## 1. Current Snapshot
1. Phase A 완료(2026-02-12), Phase B 완료(2026-02-19), Phase C 완료(2026-02-20), `D-018` 완료(2026-02-21).
2. 핵심 기준: 안정성 > 비용 > 성능, SSG 사용자 플레인 + InfluxDB SoT 유지.
3. `/status`는 운영 신호 경로, `/history`/`/predict`는 sunset tombstone(`410`).
4. `C-004` 완료: `worker-train` one-shot 실행 경계 + `train_model` CLI + runbook(`docs/RUNBOOK_TRAIN_JOB.md`) 고정.
5. `C-013`~`C-016` 완료: stale RCA 후속과 monitor escalation, timeboxed 가독성 분해까지 잠금.
6. `D-012` 완료: 학습 SoT/chunk 추출 안전장치 + MLflow SQLite tracking/partial-success/snapshot latest-only 정책 잠금, ops-train 스모크 완료(2026-02-26).
7. `D-001` 완료: Prophet 경로 `fit/predict/save/load` 계약 문서/회귀 테스트 잠금(2026-02-26).
8. `D-002` 완료: 모델 metadata/version 스키마(v1) 문서화 + sidecar 저장 경로 고정(2026-02-26).
9. `D-046` 완료: `/status`가 monitor와 동일한 Influx-JSON consistency override를 사용하도록 정렬했다(2026-03-04).
10. `D-051` in_progress: status consistency 공통 모듈 분리와 Docker-Ops 경계 정리는 문서/코드 반영이 끝났고, 로컬 스모크 증거만 남아 있다(2026-03-05).
11. 완료 증거: `PYENV_VERSION=coin pytest -q tests/test_api_status.py tests/test_status_monitor.py` 통과(`37 passed`, 2026-03-04).
12. Phase C 상세 원문은 `docs/archive/phase_c/*`로 이동했다.

## 2. Runtime Baseline (Post-Phase C)
1. cadence: `UTC boundary + detection gate`
2. worker topology: `worker-ingest` 단일 실행 경로(ingest -> publish in-cycle causal chain)
3. publish trigger: ingest stage in-cycle 후 publish reconcile 실행
4. monitor consistency current baseline: `symbol+timeframe` 기준 + `PRIMARY_TIMEFRAME` legacy fallback
5. ingest routing: `1d/1w/1M` 포함 전 timeframe direct fetch(derived downsample 경로 제거)
6. model artifact boundary: `symbol+timeframe canonical` + primary legacy fallback(`D-2026-03-03-71`)
7. `/status` 판정 parity(`D-046`)는 적용 완료됐고, next refactor lock은 scheduler `boundary` 단일 모드(`D-047`)와 legacy 제거(`D-040~D-042`)다.

## 3. Next Priority Tasks
1. `D-051`: D-046 공통 판정 모듈 분리 + Docker-Ops 의존성 경계 정리(near-done, monitor/worker-train smoke 증거 확보)
2. `D-040`: Legacy Kill Stage 1 — 모델 fallback 제거
3. `D-041`: Legacy Kill Stage 2 — static dual-write 제거
4. `D-042`: Legacy Kill Stage 3 — Influx legacy query fallback 제거(ingest+monitor)
5. `D-047`: Scheduler mode boundary 단일화(`poll_loop` 제거)
6. `D-043`: Manifest 계약 분리(`manifest.v2` 단일 파일 내 `public`/`ops`)
7. `D-044`: 상태 스키마 정규화
8. `D-045`: Orchestrator 모듈화 인터페이스 잠금
9. `D-013`: 재학습 트리거 정책 정의 — in_progress(2026-03-03), `00:35 UTC` + retry `N=2` + event catalog lock(실행 보류)

## 4. Current Risks
1. `TD-012`: 자동 재학습/승격 게이트 미구현
2. `TD-010`: 모델 추상 인터페이스/교체 경계 미구현
3. `TD-022`: prediction freshness 의미론(입력 stale 은닉 가능성) 정렬 필요
4. `TD-035`: 이벤트 기반 재학습 임계치 휴리스틱(미보정) 리스크

## 5. Runtime Notes
1. 로컬 `.env`는 참고용이며, 실제 서버 런타임은 `.env.prod` 기준 주입이다.
2. sunset 이후 운영 기본 점검은 `/status` + static 산출물 확인 경로를 사용한다.
3. 학습 실행은 상시 서비스가 아니라 one-shot runbook 절차를 따른다.
4. 고위험 구조개편은 로컬 테스트 + 로컬 스모크 통과 전 `dev` push를 금지한다(`D-2026-03-03-72`).
5. 배포 워크플로우는 `main` push(또는 수동 dispatch)만 허용한다(`D-2026-03-04-77`).
6. 로컬 스모크는 `docker-compose.local.yml` override로 로컬 Dockerfile build 이미지를 사용하되, 반드시 `docker-compose.yml`과 병합해 실행한다.
7. `docker compose -f docker-compose.local.yml ...` 단독 실행은 금지한다. 이 경로는 `worker-ingest`의 volume/env/depends_on 계약을 잃어 `/app/static_data` 누락처럼 보이는 오진을 만들 수 있다.

## 6. Quick Verify Commands
1. `PYENV_VERSION=coin pytest -q`
2. `python -m compileall api utils scripts tests`
3. `PYENV_VERSION=coin pytest -q tests/test_train_model.py`
4. `docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.prod config`

## 7. Archive Guidance
1. Phase A 상세 이력: `docs/archive/phase_a/*`
2. Phase B 상세 이력: `docs/archive/phase_b/*`
3. Phase C 상세 이력: `docs/archive/phase_c/*`
4. 활성 문서는 현재 실행 기준만 유지한다.
