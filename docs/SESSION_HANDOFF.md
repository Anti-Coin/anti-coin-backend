# Coin Predict Session Handoff

- Last Updated: 2026-02-12
- Branch: `dev`

## 1. Current Snapshot
1. Phase A(Reliability Baseline) 완료.
2. 핵심 기준: 안정성 > 비용 > 성능, SSG 사용자 플레인 + InfluxDB SoT 유지.
3. `/status`는 운영/경고 신호 노출 경로로 유지, `/history`/`/predict`는 fallback 경로.

## 2. Next Priority Tasks
1. `C-005`: worker 역할 분리(ingest/predict/export)
2. `C-006`: timeframe 경계 기반 trigger 전환
3. `B-005`: fallback endpoint sunset 정리

## 3. Current Risks
1. `TD-018`: API-SSG 운영 계약(필드/경로) 최종 확정 미완료
2. `TD-019`: 단일 worker 결합 구조로 장애 전파 가능
3. `TD-020`: 고정 poll loop로 비용/정합성 리스크

## 4. Quick Verify Commands
1. `PYENV_VERSION=coin pytest -q`
2. `python -m compileall api utils scripts tests`

## 5. Archive Guidance
1. Phase A 상세 결정/로그는 `docs/archive/phase_a/*`에서 확인한다.
2. 활성 문서에는 현재 실행 규칙만 유지한다.
