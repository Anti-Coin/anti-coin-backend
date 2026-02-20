# Runbook: Standalone Training Job (`worker-train`)

- Last Updated: 2026-02-20
- Scope: `C-004` one-shot training execution and rollback

## 1. Purpose
1. ingest/publish 운영 루프와 분리된 학습 잡을 수동으로 실행한다.
2. 학습 실행 경계를 명시해 자원 경합과 운영 혼선을 줄인다.

## 2. Preconditions
1. compose 환경 파일(`.env.prod` 또는 대상 env)에 `TRAIN_*` 값이 준비되어 있어야 한다.
2. 모델 디렉터리 백업을 먼저 생성한다.
3. 학습 실행은 one-shot으로만 수행한다(상시 서비스 금지).

## 3. Backup
1. `ts=$(date -u +%Y%m%dT%H%M%SZ)`
2. `cp -a models "models_backup_${ts}"`

## 4. Execute
1. 기본 실행
   - `docker compose --profile ops-train run --rm worker-train`
2. 대상/시간축 제한 실행
   - `docker compose --profile ops-train run --rm worker-train --symbols BTC/USDT --timeframes 1h --lookback-limit 500`

## 5. Verify
1. 실행 로그에 `[Train] completed`가 남는지 확인한다.
2. 산출물 파일 확인:
   - canonical: `models/model_{SYMBOL}_{TIMEFRAME}.json`
   - legacy(primary only): `models/model_{SYMBOL}.json`
3. 회귀 테스트:
   - `PYENV_VERSION=coin pytest -q tests/test_train_model.py`

## 6. Rollback
1. 학습 실행 중단: `ops-train` profile 호출을 중지한다.
2. 백업 복구:
   - `cp -a "<backup_dir>/." models/`
3. 복구 확인:
   - `ls models/`
   - `PYENV_VERSION=coin pytest -q tests/test_train_model.py`

## 7. Notes
1. 자동 재학습/스케줄링은 본 runbook 범위가 아니다(`D-006`, `D-007`).
2. 승격 게이트(모델 채택 판단)는 본 runbook 범위가 아니다(`D-005`).
