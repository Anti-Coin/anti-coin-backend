# Coin Predict Session Handoff

- Last Updated: 2026-02-20
- Branch: `dev`

## 1. Current Snapshot
1. Phase A 완료(2026-02-12), Phase B 완료(2026-02-19), Phase C 완료(2026-02-20).
2. 핵심 기준: 안정성 > 비용 > 성능, SSG 사용자 플레인 + InfluxDB SoT 유지.
3. `/status`는 운영 신호 경로, `/history`/`/predict`는 sunset tombstone(`410`).
4. `C-004` 완료: `worker-train` one-shot 실행 경계 + `train_model` CLI + runbook(`docs/RUNBOOK_TRAIN_JOB.md`) 고정.
5. `C-013`~`C-016` 완료: stale RCA 후속과 monitor escalation, timeboxed 가독성 분해까지 잠금.
6. 완료 증거: `PYENV_VERSION=coin pytest -q` 통과(`137 passed`, 2026-02-20).
7. Phase C 상세 원문은 `docs/archive/phase_c/*`로 이동했다.

## 2. Runtime Baseline (Post-Phase C)
1. cadence: `UTC boundary + detection gate`
2. worker topology: `worker-ingest`/`worker-publish` 2-service
3. publish trigger: ingest watermark advance gate
4. monitor consistency: `symbol+timeframe` 기준 + `PRIMARY_TIMEFRAME` legacy fallback

## 3. Next Priority Tasks
1. `D-001`: 모델 인터페이스 계약(`fit/predict/save/load`) 고정
2. `D-002`: 모델 메타데이터/버전 스키마 정의
3. `D-012`: 학습 데이터 SoT 정렬(Influx 기반 closed-candle snapshot)
4. `D-013`: 재학습 트리거 정책 정의(시간+이벤트)

## 4. Current Risks
1. `TD-012`: 자동 재학습/승격 게이트 미구현
2. `TD-010`: 모델 인터페이스 미구현
3. `TD-030`: 장기 TF 샘플 부족 차단/품질표시 미구현
4. `TD-009`: dev push 즉시 배포 구조 리스크

## 5. Runtime Notes
1. 로컬 `.env`는 참고용이며, 실제 서버 런타임은 `.env.prod` 기준 주입이다.
2. sunset 이후 운영 기본 점검은 `/status` + static 산출물 확인 경로를 사용한다.
3. 학습 실행은 상시 서비스가 아니라 one-shot runbook 절차를 따른다.

## 6. Quick Verify Commands
1. `PYENV_VERSION=coin pytest -q`
2. `python -m compileall api utils scripts tests`
3. `PYENV_VERSION=coin pytest -q tests/test_train_model.py`

## 7. Archive Guidance
1. Phase A 상세 이력: `docs/archive/phase_a/*`
2. Phase B 상세 이력: `docs/archive/phase_b/*`
3. Phase C 상세 이력: `docs/archive/phase_c/*`
4. 활성 문서는 현재 실행 기준만 유지한다.
