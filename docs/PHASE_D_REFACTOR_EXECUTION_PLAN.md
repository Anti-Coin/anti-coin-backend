# Phase D Refactor Execution Plan

- Last Updated: 2026-03-04
- Scope: `legacy kill` -> `manifest.v2 contract split` -> `modularization`
- Status: Planned (execution gated by local smoke)

## 1. Why This Plan Exists
1. 변경 규모가 커서 한번에 서버 반영하면 원인 분리가 어렵다.
2. 자동 배포(dev push) 리스크를 줄이기 위해 로컬 검증을 선행한다.
3. 조용한 fallback과 중복 상태를 제거해 모델 단계 안정성을 높인다.

## 2. Global Guardrails
1. 순서 고정: Track A(`legacy kill`) -> Track B(`contract split`) -> Track C(`modularization`)
2. 기본 흐름: feature branch -> 로컬 테스트 -> 로컬 스모크 -> 문서 동기화 -> `dev` push
3. 단계별 롤백 경계: track stage 단위 커밋
4. Fail-Closed 우선: fallback 제거 후 누락은 `model_missing`/차단으로 노출
5. one task, one purpose: 기능 변경과 구조 변경을 동일 단계에서 섞지 않는다

## 3. Track A: Legacy Kill
### 3.1 Objective
1. legacy fallback/dual-write 경로를 제거하고 canonical 계약만 남긴다.
2. `/status`와 monitor 판정 경로를 monitor 기준으로 단일화한다.
3. scheduler mode를 `boundary` 단일값으로 잠근다.

### 3.2 Stages
1. `LK-0` 사전 충족 검사
   - 대상: 운영 symbol/timeframe별 canonical 모델/산출물 존재 여부 점검
   - Gate: 누락이 있으면 Track A 진입 금지
2. `LK-1` 모델 fallback 제거
   - 변경 대상: `workers/predict.py`
   - 변경 내용: `model_{symbol}_{timeframe}.json` only, legacy model fallback 제거
3. `LK-2` static dual-write 제거
   - 변경 대상: `workers/predict.py`, `workers/export.py`, static read helpers
   - 변경 내용: canonical write/read only
4. `LK-3` legacy query fallback 제거
   - 변경 대상: `workers/ingest.py`
   - 변경 내용: Influx no-timeframe fallback query 제거(ingest + monitor)
5. `LK-4` status/monitor parity 적용
   - 변경 대상: `api/main.py`, `scripts/status_monitor.py`, `utils/prediction_status.py`
   - 변경 내용: 동일 evaluator + 동일 Influx-JSON consistency rule 적용, Influx query 실패 시 JSON 판정 유지
6. `LK-5` scheduler mode hard lock
   - 변경 대상: `scripts/worker_config.py`, `scripts/pipeline_worker.py`
   - 변경 내용: `WORKER_SCHEDULER_MODE=boundary` 단일화, `poll_loop`/invalid fallback 제거(fail-fast)
7. `LK-6` 문서/테스트 정리
   - 변경 대상: `docs/MODEL_CONTRACT.md`, 관련 테스트

### 3.3 Verification
1. Unit/regression:
   - `PYENV_VERSION=coin pytest -q tests/test_model_contract.py tests/test_pipeline_worker.py tests/test_api_status.py tests/test_status_monitor.py`
2. Local smoke:
   - `docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.prod --profile ops-train run --rm worker-train --symbols BTC/USDT --timeframes 1h,1d,1w,1M`
   - `docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.prod up -d --build worker-ingest`
   - canonical 산출물/`model_missing` 차단 로그 확인
   - `/status`와 monitor 동일 입력에 대한 상태 일치 확인

### 3.4 Rollback
1. 해당 stage 커밋 revert
2. canonical 누락이 원인이면 LK-0 보강 후 재시도

## 4. Track B: Contract Split
### 4.1 Objective
1. 단일 `manifest.v2` payload 내에서 FE/OPS 계약을 분리한다.
2. 파일 개수 증가는 피하고 1회 atomic write를 유지한다.

### 4.2 Stages
1. `CS-0` schema lock
   - 산출물: `manifest.v2.public`(최소 필드), `manifest.v2.ops`(상세 필드) 문서화
2. `CS-1` writer split
   - 변경 대상: `workers/export.py`
   - 변경 내용: 단일 파일 내 `public/ops` 섹션 동시 생성
3. `CS-2` consumer migration
   - 변경 대상: FE 경로, `admin/app.py`, `admin/manifest_view.py`
   - 변경 내용: FE는 `manifest.v2.public`만, admin/ops는 `manifest.v2.ops`만 사용
4. `CS-3` 구계약 정리
   - 변경 대상: runbook/tests/docs
   - 변경 내용: 구 `manifest` 평면 필드 의존 제거

### 4.3 Verification
1. Unit/regression:
   - `PYENV_VERSION=coin pytest -q tests/test_manifest_view.py tests/test_api_status.py tests/test_pipeline_worker.py`
2. Local smoke:
   - `manifest.v2.public/ops` 섹션 생성 및 필드 계약 검증
   - admin 화면 필터/매트릭스 정상 동작 확인

### 4.4 Rollback
1. consumer migration 전까지는 dual-publish 유지
2. migration 실패 시 consumer만 직전 경로로 복구

## 5. Track C: Modularization
### 5.1 Objective
1. 대형 파일 책임을 분리해 변경 영향 반경과 컨텍스트 비용을 줄인다.

### 5.2 Stages
1. `MZ-0` 인터페이스 잠금
   - `model_io`, `state_store`, `policy_eval`, `orchestrator` 경계 문서화
2. `MZ-1` state store 통합
   - 상태 파일 I/O를 저장소 계층으로 통일
3. `MZ-2` model I/O 모듈 분리
   - 모델 경로 해석/저장/로드 계약 단일화
4. `MZ-3` orchestrator 슬림화
   - `pipeline_worker`는 조합/호출 역할 중심으로 축소
5. `MZ-4` 구조 게이트 추가
   - 함수 길이/모듈 의존 방향/복잡도 체크 추가

### 5.3 Verification
1. Unit/regression:
   - `PYENV_VERSION=coin pytest -q`
2. Local smoke:
   - worker 1 cycle 정상
   - 상태 파일 write/read 불변식 확인

### 5.4 Rollback
1. 인터페이스 경계 커밋 단위로 revert
2. store/worker 경계에서 계약 테스트 깨지면 바로 중단

## 6. Local Smoke Checklist (Before Any Dev Push)
1. 테스트: 핵심 테스트 묶음 전부 통과
2. worker-train one-shot 통과
3. worker-ingest 1 cycle 이상 정상 완료
4. 상태 파일 스키마 검증 통과
5. 변경 문서(`DECISIONS/PLAN/TASKS/HANDOFF`) 동기화 완료

## 7. Exit Criteria
1. Track A~C 각 stage Done Condition 충족
2. fallback 제거 후에도 오노출 0 유지
3. 운영자 관측성 저하 없이 구조 단순화 완료
