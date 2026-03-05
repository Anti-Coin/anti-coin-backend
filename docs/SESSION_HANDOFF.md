# Coin Predict Session Handoff

- Last Updated: 2026-03-05
- Branch: `dev`

## 1. Current Snapshot
1. Phase A 완료(2026-02-12), Phase B 완료(2026-02-19), Phase C 완료(2026-02-20), `D-018` 완료(2026-02-21).
2. 핵심 기준: 안정성 > 비용 > 성능, SSG 사용자 플레인 + InfluxDB SoT 유지.
3. `/status`는 운영 신호 경로, `/history`/`/predict`는 sunset tombstone(`410`).
4. `C-004` 완료: `worker-train` one-shot 실행 경계 + `train_model` CLI + runbook(`docs/RUNBOOK_TRAIN_JOB.md`) 고정.
5. `C-013`~`C-016` 완료: stale RCA 후속과 monitor escalation, timeboxed 가독성 분해까지 잠금.
6. `D-012` 완료: 학습 SoT/chunk 추출 안전장치 + MLflow SQLite tracking/partial-success/snapshot latest-only 정책 잠금, ops-train 스모크 완료(2026-02-26).
7. `D-001` 완료: Prophet 경로 `fit/predict/save/load` 계약 문서/회귀 테스트 잠금(2026-02-26).
8. `D-002` 완료: 모델 metadata/version 스키마(v1) 문서화 + sidecar 저장 경로 고정(2026-02-26).
9. 완료 증거: `PYENV_VERSION=coin pytest -q` 통과(`140 passed`, 2026-02-21).
10. Phase C 상세 원문은 `docs/archive/phase_c/*`로 이동했다.

## 2. Runtime Baseline (Post-Phase C)
1. cadence: `UTC boundary + detection gate`
2. worker topology: `worker-ingest` 단일 실행 경로(ingest -> publish in-cycle causal chain)
3. publish trigger: ingest stage in-cycle 후 publish reconcile 실행
4. monitor consistency current baseline: `symbol+timeframe` 기준(legacy query fallback 제거)
5. ingest routing: `1d/1w/1M` 포함 전 timeframe direct fetch(derived downsample 경로 제거)
6. model artifact boundary: `symbol+timeframe canonical` (train/predict canonical-only)
7. next refactor lock: `/status` 판정은 monitor 기준 parity로 전환(`D-046`), scheduler는 `boundary` 단일 모드로 잠금(`D-047`)

## 3. Next Priority Tasks
1. `D-013`: 재학습 트리거 정책 정의 — in_progress(2026-03-03), `00:35 UTC` + retry `N=2` + event catalog lock(실행 보류)
2. `D-046`: Status-Monitor 판정 경로 단일화(모니터 기준)
3. `D-040`: Legacy Kill Stage 1 — 모델 fallback 제거
4. `D-041`: Legacy Kill Stage 2 — static dual-write 제거
5. `D-042`: Legacy Kill Stage 3 — Influx legacy query fallback 제거(ingest+monitor)
6. `D-043`: Manifest 계약 분리(`manifest.v2` 단일 파일 내 `public`/`ops`)
7. `D-047`: Scheduler mode boundary 단일화(`poll_loop` 제거)
8. `D-044`: 상태 스키마 정규화
9. `D-045`: Orchestrator 모듈화 인터페이스 잠금

## 4. Current Risks
1. `TD-012`: 자동 재학습/승격 게이트 미구현
2. `TD-010`: 모델 인터페이스 미구현
3. `TD-022`: prediction freshness 의미론(입력 stale 은닉 가능성) 정렬 필요
4. `TD-035`: 이벤트 기반 재학습 임계치 휴리스틱(미보정) 리스크

## 5. Runtime Notes
1. 로컬 `.env`는 참고용이며, 실제 서버 런타임은 `.env.prod` 기준 주입이다.
2. sunset 이후 운영 기본 점검은 `/status` + static 산출물 확인 경로를 사용한다.
3. 학습 실행은 상시 서비스가 아니라 one-shot runbook 절차를 따른다.
4. 고위험 구조개편은 로컬 테스트 + 로컬 스모크 통과 전 `dev` push를 금지한다(`D-2026-03-03-72`).
5. 배포 워크플로우는 `main` push(또는 수동 dispatch)만 허용한다(`D-2026-03-04-77`).
6. 로컬 스모크는 `docker-compose.local.yml` override로 로컬 Dockerfile build 이미지를 사용한다.

## 6. Quick Verify Commands
1. `PYENV_VERSION=coin pytest -q`
2. `python -m compileall api utils scripts tests`
3. `PYENV_VERSION=coin pytest -q tests/test_train_model.py`

## 7. Archive Guidance
1. Phase A 상세 이력: `docs/archive/phase_a/*`
2. Phase B 상세 이력: `docs/archive/phase_b/*`
3. Phase C 상세 이력: `docs/archive/phase_c/*`
4. 활성 문서는 현재 실행 기준만 유지한다.
