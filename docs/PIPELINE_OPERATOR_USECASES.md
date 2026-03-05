# Pipeline Operator Usecases (Baseline)

- Last Updated: 2026-03-05
- Scope: 운영자 관점 실행 계약(ingest/predict/export/serve/monitor) + 실패 전파 규칙 + 상태 축소 우선순위
- Purpose: Legacy kill/계약 잠금 이후 구조개편(D-044~D-045)의 기준선을 고정한다.

## 1. Why This Document Exists
1. 현재 pipeline은 fallback/호환 경로가 누적되어 의도 파악 비용이 높다.
2. "어떤 실패를 차단하고, 어떤 실패를 degraded로 노출할지"를 단계별로 고정해야 한다.
3. 이후 모듈화/인터페이스화/상태파일 축소 작업은 이 계약을 깨지 않는 범위에서만 진행한다.

## 2. Non-Negotiables
1. 우선순위: Stability > Cost > Performance.
2. Source of Truth: InfluxDB.
3. 사용자 데이터 플레인: static JSON(nginx 서빙).
4. No silent failure: 모든 실패는 `stage + cause + impact`로 기록한다.
5. UTC internally.

## 3. Policy Lock Matrix
| Topic | Rule | Status |
|---|---|---|
| canonical model missing | `fail-closed` (`model_missing`) | locked |
| prediction stage failure | `last-good + degraded` 허용 (상태/사유 노출 필수) | locked |
| export stage failure | 영향 symbol/timeframe `serve_allowed=false` 강제(`hard block`) | locked |
| state file reduction order | `prediction_health 중복 identity -> symbol_activation 중복/파생 -> 기타` | locked |

## 4. Stage Contract (Operator Runtime)
### 4.1 Stage 0: Preflight
1. 환경변수/설정값 스키마 검증.
2. scheduler mode, target set, 경로 권한, 필수 의존성 점검.
3. no-overlap 락 검증.
4. 실패 시 `fail-fast`로 종료.

### 4.2 Stage 1: Target Resolution
1. 실행 대상(`symbol x timeframe`) 확정.
2. symbol activation 상태 로드(visibility/state/coverage).
3. hidden_backfilling은 사용자 노출 경로를 사전 차단.

### 4.3 Stage 2: Ingest Decision
1. 케이스 분기:
1. cold start (DB/state 모두 없음)
2. warm restart (DB 데이터 있음)
3. state drift (state cursor와 DB 불일치)
4. backward coverage gap (earliest 불일치)
5. storage guard block
6. exchange detection unavailable
2. `since` 기준은 SoT(DB latest/earliest) 우선, 상태파일은 보조 기준.

### 4.4 Stage 3: Ingest Execute + Quality
1. exchange fetch -> closed candle filter -> gap detect/refill -> SoT write.
2. ingest cursor/status 즉시 커밋.
3. 실패/skip/block 모두 reason code를 기록.
4. long TF에서는 detection skip이어도 backward gap이면 ingest override 허용.

### 4.5 Stage 4: Predict Eligibility
1. canonical 모델 존재 여부 확인(legacy fallback 제거 방향).
2. min sample gate.
3. activation visibility/serve boundary 확인.
4. ingest 결과 미충족 시 predict 차단 또는 정책적 skip.

### 4.6 Stage 5: Predict Execute
1. 성공: prediction artifact + Influx prediction 저장.
2. 실패: `degraded=true`, `last_error`, `consecutive_failures` 갱신.
3. 정책: `last-good + degraded` 허용(침묵 금지).

### 4.7 Stage 6: Export Execute
1. SoT 기반 history/prediction/manifest 산출물 반영.
2. export 실패는 stage 원인으로 기록하고 게이트에 반영.
3. 강제 정책: 영향 key `serve_allowed=false` (hard block).

### 4.8 Stage 7: Serve Decision
1. 최종 비트는 `serve_allowed`.
2. 기준 신호:
1. visibility
2. prediction freshness/status
3. degraded policy
4. export/write health
3. fail-closed 우선: 오노출 의심 시 차단.

### 4.9 Stage 8: Monitor/Alert (Cross-Cutting)
1. monitor는 별도 단계가 아니라 전 단계를 관통하는 관측 기능.
2. 이벤트 최소 스키마:
1. `stage` (ingest/predict/export/serve)
2. `cause` (model_missing, influx_query_error, export_write_failed ...)
3. `impact` (predict_skipped, serve_blocked, degraded ...)
3. 알림은 "서빙까지 무조건 전파"가 아니라 "원인/영향을 분리해 기록 + 정책적 차단"을 원칙으로 한다.

## 5. Operator Usecase Catalog
### UC-ING-01 Cold Start
1. DB/state 모두 비어 있음.
2. exchange earliest 또는 lookback bootstrap으로 시작.
3. activation은 hidden_backfilling 유지.

### UC-ING-02 Warm Restart
1. 배포 재기동, DB 데이터 존재.
2. DB last 기준 증분 수집.
3. state drift면 DB를 SoT로 재정렬.

### UC-ING-03 Data Missing Backfill
1. gap detector가 누락 구간을 식별.
2. refill 수행 후 잔존 gap 재검증.
3. 잔존 시 경고 + 재시도 정책 적용.

### UC-ING-04 Storage Pressure
1. disk watermark `warn/critical/block`.
2. block에서는 신규 고비용 backfill 차단.
3. 기존 서비스 영향 최소화 우선.

### UC-PRED-01 Model Missing
1. canonical model 없음.
2. 즉시 `model_missing` fail-closed.

### UC-PRED-02 Insufficient Data
1. timeframe min sample 미달.
2. `skipped(insufficient_data)` + 상태 노출.

### UC-PRED-03 Prediction Failure
1. 예측 에러 발생.
2. last-good 유지 + degraded 전이 + 알림.

### UC-EXP-01 Export Failure
1. static artifact write 실패.
2. 원인(stage=export) 기록.
3. 강제: 영향 key `serve_allowed=false`.

### UC-MON-01 Status Consistency Mismatch
1. JSON vs Influx 시각 갭이 hard limit 초과.
2. hard_stale로 승격.
3. Influx unavailable이면 JSON 판정 유지.

### UC-OPS-01 Scheduler Misconfig
1. invalid mode/config 감지.
2. fallback 대신 fail-fast 종료.

## 6. State File Reduction Baseline
1. 1순위: `prediction_health`의 redundant identity 필드 제거(`symbol`, `timeframe`).
2. 2순위: `symbol_activation`의 중복/파생 필드 정규화(`state` 단일 SoT 기준).
3. 3순위: `ingest_watermarks`/`runtime_metrics`는 인과/운영 증거 대체 경로 입증 전 유지.

## 7. Docker-Ops Baseline (Usecase-Aligned)
1. API/monitor/worker가 공통 판정 함수를 사용할 때, monitor 엔트리포인트 모듈 직접 import를 피하고 `utils/*` 공유 모듈로 분리한다.
2. 이미지별 의존성 경계를 유지한다.
1. fastapi image: API 런타임 필수 의존성만 포함
2. worker image: train/monitor/ingest 의존성 포함
3. smoke gate:
1. local image build (`docker-compose.local.yml`)
2. fastapi import smoke
3. worker-ingest 1 cycle
4. monitor 1 cycle
5. worker-train one-shot

## 8. Change Gate for Refactor
1. 이 문서의 stage 계약을 깨는 변경은 `DECISIONS + TASKS + 테스트` 동시 업데이트가 없으면 금지.
2. 리팩토링은 "행동 불변"과 "행동 변경"을 같은 patch에 섞지 않는다.
3. 고위험 변경은 stage 단위 커밋/롤백 경계를 유지한다.

## 9. Refactor Candidate Matrix (Usecase-Driven)
### 9.1 Common Module Candidates
| Candidate | Current Spread | Proposed Module | Gate |
|---|---|---|---|
| status consistency 판단(`evaluate + influx/json override`) | `api/main.py`, `scripts/status_monitor.py` | `utils/status_consistency.py` | API가 `scripts.*` import 없이 동작 |
| stage event schema(`stage/cause/impact`) | worker/monitor 로그 분산 | `utils/pipeline_events.py` | 모든 실패 로그가 공통 스키마 준수 |
| model path/loader 정책 | predict/train 양쪽 분산 | `utils/model_store.py` | canonical-only 전환 회귀 통과 |
| serve gate 조합 규칙 | manifest/status 경로 분산 | `utils/serve_policy.py` | `serve_allowed` 계산 경로 단일화 |

### 9.2 Interface Candidates
| Interface | Responsibility | Consumers |
|---|---|---|
| `StateStore` | activation/health/watermark read-write 계약 | worker, admin |
| `ModelStore` | model/meta resolve/load/save 계약 | train, predict |
| `PolicyEvaluator` | freshness/degraded/serve gate 정책 평가 | api, monitor, export |
| `IngestCursorResolver` | since/source 판정 + drift/rebootstrap 정책 | worker ingest |

### 9.3 Env/Constant Reduction Candidates
1. 중복 노출 제거: `worker_config`와 `utils.config` 재노출 상수 정리.
2. scheduler 관련 값은 boundary 단일 계약 기준으로 축소.
3. train 전용/serve 전용/env 네임스페이스 분리(`TRAIN_*`, `SERVE_*`, `MONITOR_*`).
4. 운영 불변값은 문서 잠금 후 코드 상수로 승격하고 env 가변 범위를 축소.

### 9.4 Fallback Retirement Candidates
1. model legacy fallback (`model_{symbol}.json`) -> 제거(`D-040`).
2. static dual-write/read legacy 경로 -> 제거(`D-041`).
3. Influx no-timeframe legacy query -> 제거(`D-042`).
4. scheduler invalid/poll_loop fallback -> 제거(`D-047`).

### 9.5 State File Reduction Candidates
1. `prediction_health`: `symbol`, `timeframe` 제거(키 기반 identity).
2. `symbol_activation`: `state` 단일 SoT로 두고 `visibility/is_full_backfilled` 파생 전환 검토.
3. `ingest_watermarks`: 대체 인과 경계 입증 전 유지.
4. `runtime_metrics.recent_cycles`: 운영 보존 윈도우 축소 후보.

### 9.6 Compose/Ops Reliability Candidates
1. `depends_on: service_started`를 `service_healthy` 경계로 강화.
2. InfluxDB healthcheck 추가 후 worker/fastapi/monitor 의존성 연결.
3. local smoke는 반드시 base+local 파일을 함께 사용:
1. `docker compose -f docker-compose.yml -f docker-compose.local.yml ...`
2. `docker compose -f docker-compose.local.yml ...` 단독 실행 금지.
