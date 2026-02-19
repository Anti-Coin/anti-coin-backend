# Coin Predict Task Board (Active)

- Last Updated: 2026-02-19
- Rule: 활성 태스크만 유지하고, 완료 상세 이력은 Archive로 분리
- Full Phase A History: `docs/archive/phase_a/TASKS_MINIMUM_UNITS_PHASE_A_FULL_2026-02-12.md`

## 0. Priority
1. P0: 안정성/무결성 즉시 영향
2. P1: 확장성/운영성 핵심 영향
3. P2: 품질/가독성/자동화 개선

## 1. Milestone Snapshot
1. Phase A(Reliability Baseline) 완료 (2026-02-12)
2. A-001~A-019 완료
3. 검증 근거: `PYENV_VERSION=coin pytest -q` -> `58 passed`
4. `R-001` 완료 (2026-02-12): B/C/D Phase 목적/Exit 조건 재검증을 `PLAN`에 반영
5. `R-002` 완료 (2026-02-12): B/C/D 활성 태스크에 `why/failure/verify/rollback` 설계 카드 반영
6. `R-003` 완료 (2026-02-12): 교차 Phase 우선순위 2안 비교 후 Option A(phase-ordered stability) 기준선 채택
7. `R-004` 완료 (2026-02-12): Phase B kickoff 구현 묶음(`B-002 -> B-003`)과 검증/롤백 경계 확정
8. `D-2026-02-13-29` 채택: 1m 비대칭 정책(예측 비서빙 + hybrid 서빙 후보)과 저장소 가드가 Phase B 선행 조건임을 확정
9. `D-2026-02-13-30` 채택: 서빙 정책을 Hard Gate + Accuracy Signal 2층 구조로 고정
10. `B-001` 정책 매트릭스 초안(v1) 작성: `docs/TIMEFRAME_POLICY_MATRIX.md`
11. `D-2026-02-13-32` 채택: Phase D 모델 커버리지를 `shared -> dedicated 승격` 전략으로 고정
12. `B-002` 완료 (2026-02-13): canonical `{symbol}_{timeframe}` 네이밍 적용 + legacy 호환(dual-write) + 회귀 테스트(`29 passed`) 확인
13. `B-003` 완료 (2026-02-13): 다중 timeframe(`1h/1d/1w/1M`) + 5개 symbol 실운영 cycle 확인(약 30초), `1m` prediction 비생성 정책 반영, 회귀 `66 passed`
14. `B-001` 진행 (2026-02-13): config gate를 env 기반으로 전환(`ENABLE_MULTI_TIMEFRAMES`), 기본값은 `1h` 고정 유지
15. `D-2026-02-13-33` 채택: cycle cadence를 `boundary + detection gate` 하이브리드로 확정(`C-006 -> C-007`)
16. `B-004` 완료 (2026-02-13): worker cycle마다 `manifest.json` 생성(심볼/타임프레임별 history/prediction 상태 + degraded 병합), 회귀 `68 passed`
17. `B-006` 완료 (2026-02-13): `1m` retention(기본 14d, 상한 30d clamp) + 디스크 워터마크(70/85/90) 가드 + `block` 레벨에서 `1m` 초기 백필 차단 반영 + `1h->1d/1w/1M` downsample + `downsample_lineage.json` 경로 및 검증 테스트 반영, 회귀 `76 passed`
18. `D-2026-02-13-34` 채택: reconciliation mismatch를 내부/외부로 분리(`internal_deterministic_mismatch` vs `external_reconciliation_mismatch`)하고, `1d/1w/1M` direct ingest 금지 경계를 정책으로 고정
19. `C-002` 진행 (2026-02-13): `runtime_metrics.json` baseline 추가(실행시간/실패율/overrun 추세, poll-loop 모드에서 `missed_boundary`는 미지원으로 명시)
20. `I-2026-02-13-01` 반영: `1h` canonical underfill(예: 30d 대비 소량 row) 시 DB last가 있어도 lookback 재부트스트랩을 강제해 bootstrap drift를 복구
21. `D-2026-02-13-35` 채택: `I-2026-02-13-01`은 임시 방편(containment)이며 RCA 완료 전 최종 해결로 간주하지 않음
22. `D-2026-02-17-36` 채택: 모든 심볼 onboarding을 `1h full-first(exchange earliest)`로 고정하고, full backfill 완료 전 FE 심볼 완전 비노출 게이트를 정책으로 채택
23. `B-001` 진행 (2026-02-17): worker에 symbol activation(`registered/backfilling/ready_for_serving`) 및 manifest `visibility/is_full_backfilled/coverage_*` 필드 반영, hidden 심볼 `serve_allowed=false` 강제, 회귀 `87 passed`
24. `B-001` 완료 (2026-02-17): 정책/구현/회귀 근거(`87 passed`)가 정렬되어 timeframe 정책 잠금 태스크를 종료
25. `C-008` 시작 (2026-02-17): `1h underfill` RCA 착수(`I-2026-02-13-01` 임시 guard의 유지/조정/제거 결론 도출 준비)
26. `C-008` 완료 (2026-02-17): fallback 오염 경로 차단 + 회귀(`89 passed`) + `D-2026-02-17-37` 반영, guard 7일 관찰은 차단 게이트가 아닌 운영 메모로 `C-002`에서 병행 추적
27. `C-002` 완료 (2026-02-17): `runtime_metrics.json`에 `ingest_since_source_counts`/`rebootstrap`/`underfill_guard_retrigger` 집계를 추가해 `C-008` 후속 7일 관찰 근거를 메트릭 경로로 고정, 회귀 `90 passed`
28. `C-006` 완료 (2026-02-17): boundary scheduler(`WORKER_SCHEDULER_MODE=boundary` 기본) 도입으로 timeframe 경계 시점에만 실행하도록 전환, `runtime_metrics.json`에 `missed_boundary_count/rate` 실측 반영, 회귀 `93 passed`
29. `C-007` 완료 (2026-02-17): boundary 직전 detection gate(run/skip) 결합, `runtime_metrics.json`에 `detection_gate_{run,skip}_counts/events` 집계 반영 + `missed_boundary=0` 경계 시나리오 회귀 추가, 회귀 `99 passed`
30. `C-005` 완료 (2026-02-17): `WORKER_EXECUTION_ROLE`(`all`/`ingest`/`predict_export`) 분리, `run_ingest_step`으로 base ingest(`1m`,`1h`) vs derived materialization(`1d/1w/1M`) 경계 강제, ingest-only는 `runtime_metrics/symbol_activation`, publish-only는 `manifest` 갱신 책임으로 분리, 회귀 `103 passed`
31. `C-005` 확장 완료 (2026-02-17): 전용 엔트리포인트(`worker_ingest.py`, `worker_predict.py`, `worker_export.py`, `worker_publish.py`) 추가 + ingest watermark 기반 publish gate(`ingest/predict/export watermarks`) 적용 + compose 2-service(`worker-ingest`, `worker-publish`) 전환, 회귀 `106 passed`
32. `C-005` 코드 구조 정리 완료 (2026-02-17): `workers/ingest.py`, `workers/predict.py`, `workers/export.py`로 도메인 로직을 이동하고 `scripts/pipeline_worker.py`는 orchestrator + runtime glue 래퍼 중심으로 축소, 회귀 `106 passed`
33. `D-2026-02-19-39` 채택: multi-timeframe freshness 기본 임계값(`1w/1M`)을 고정하고 `4h`는 legacy compatibility 경로로 유지(soft/hard: `1w=8d/16d`, `1M=35d/70d`), 관련 설정값(`utils/config.py`, `.env.example`) 동기화
34. `C-009` 완료 (2026-02-19): monitor Influx-JSON consistency를 `symbol+timeframe` 기준으로 보강하고 `PRIMARY_TIMEFRAME` legacy fallback을 유지, 회귀 `108 passed`
35. `D-2026-02-19-40` 채택: monitor 대사 기준을 timeframe-aware로 고정
36. `C-011` 완료 (2026-02-19): boundary scheduler 시작 기준을 "다음 경계"에서 "현재 경계"로 조정해 재시작 직후 장주기 TF(`1d/1w/1M`) missed boundary를 첫 cycle에서 따라잡도록 보강, 회귀 `109 passed`
37. `R-005` 완료 (2026-02-19): SLA-lite baseline을 user plane availability 중심으로 고정(공식/데이터 소스/산출 주기 잠금), `D-2026-02-19-41` 반영
38. `B-007` 완료 (2026-02-19): admin 대시보드를 manifest-first로 전환해 symbol/timeframe/status 필터, timeframe 상태 매트릭스, prediction updated 지연 테이블을 제공하고 회귀 `113 passed`로 검증
39. `I-2026-02-19-02` 반영: streamlit Docker packaging을 `/app/admin` 구조로 고정해 `admin.manifest_view` import 오류를 제거(`docker/Dockerfile.streamlit`)

## 2. Active Tasks
### Rebaseline (Post-Phase A)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| R-001 | P0 | B/C/D Phase 목적 및 Exit 조건 재검증 | done (2026-02-12) | B/C/D Objective/Exit 재정의가 `docs/PLAN_LIVING_HYBRID.md`에 반영됨 |
| R-002 | P0 | B/C/D 태스크 재세분화(리스크 반영) | done (2026-02-12) | 활성 태스크별 `why/failure/verify/rollback` 설계 카드가 본 문서 Section 6에 반영됨 |
| R-003 | P0 | 교차 Phase 의존성/우선순위 재정렬 | done (2026-02-12) | Option A/B 비교 및 채택 기준선이 본 문서 Section 7에 반영됨 |
| R-004 | P1 | Phase B kickoff 구현 묶음 확정 | done (2026-02-12) | `B-002 -> B-003` kickoff 묶음과 검증/롤백 경계가 본 문서 Section 8에 반영됨 |
| R-005 | P1 | SLA-lite 지표 baseline 정의 | done (2026-02-19) | availability/alert miss/MTTR-stale의 공식/데이터 소스/산출 주기가 user plane 기준으로 고정되고 `daily rollup + weekly review` cadence가 문서화됨 |

### Phase B (Timeframe Expansion)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| B-001 | P1 | timeframe tier 정책 매트릭스 확정(수집/보존/서빙/예측) | done (2026-02-17) | `docs/TIMEFRAME_POLICY_MATRIX.md` 정책 잠금 + `1m` 예측 비서빙, `1m` hybrid API=`latest closed 180 candles`, `1m` rolling=`default 14d / cap 30d`, `1h` onboarding=`full-first(exchange earliest)` + `registered/backfilling/ready_for_serving` 게이트 + full backfill 완료 전 FE 심볼 완전 비노출, `1h->1d/1w/1M` downsample 경로, `1d/1w/1M` direct ingest 금지 경계, `internal_deterministic_mismatch`/`external_reconciliation_mismatch` 구분 규칙, Hard Gate+Accuracy 정책을 문서/설정으로 고정 |
| B-002 | P1 | 파일 네이밍 규칙 통일 | done (2026-02-13) | canonical `{symbol}_{timeframe}` 파일 생성 + legacy fallback 호환 유지 + `tests/test_api_status.py`/`tests/test_status_monitor.py` 회귀 통과 |
| B-003 | P1 | history/prediction export timeframe-aware 전환 | done (2026-02-13) | 다중 timeframe(`1h/1d/1w/1M`) 동시 export 동작 확인 + `1m` prediction 비생성 정책 코드/테스트 반영 + 회귀 `66 passed` |
| B-004 | P1 | manifest 파일 생성 | done (2026-02-13) | `static_data/manifest.json`에 심볼/타임프레임별 `history.updated_at`, `prediction.status/updated_at/age`, `degraded`, `serve_allowed`, `summary(status_counts)`가 주기적으로 갱신됨 |
| B-007 | P2 | 운영 대시보드(admin) timeframe 확장 | done (2026-02-19) | `admin/app.py`가 `manifest.json` 1차 소스를 사용해 symbol/timeframe/status 필터, timeframe별 freshness/degraded/serve_allowed 상태 매트릭스, prediction updated 지연 테이블을 제공하며 `tests/test_manifest_view.py` + 전체 회귀 `113 passed`로 검증됨 |
| B-008 | P2 | FE 심볼 노출 게이트 연동(`hidden_backfilling` 필터) | open | FE 심볼 리스트가 `manifest.visibility`를 소비해 `hidden_backfilling` 심볼을 완전 비노출하며, `ready_for_serving` 전환 시 자동 노출 복귀가 검증된다 |
| B-006 | P1 | 저장소 예산 가드(50GB) + retention/downsample 실행 | done (2026-02-13) | `1m` rolling(`14d default / 30d cap`) 적용 + 디스크 watermark 경보/차단 + `1h->1d/1w/1M` downsample job 및 `downsample_lineage.json` 기반 lineage/검증 경로 확정 |
| B-005 | P2 | `/history`/`/predict` fallback 정리(sunset) | open | Endpoint Sunset 체크리스트 조건 충족 + fallback 비의존 운영 1 cycle 검증 + rollback 절차 문서화 |

### Phase C (Scale and Ops)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| C-001 | P1 | 심볼 목록 확장 자동화 | open | 심볼 추가 시 코드 수정 최소화 |
| C-002 | P1 | 실행시간/실패율 메트릭 수집 | done (2026-02-17) | `static_data/runtime_metrics.json`에 cycle 실행시간/실패율/overrun 추세가 누적되고, poll-loop 기준 `missed_boundary` 미지원이 명시되며, `ingest_since_source_counts`/`rebootstrap_events`/`underfill_guard_retrigger_*`가 함께 집계되어 `C-008` 후속 관찰 근거를 제공한다 |
| C-003 | P2 | 부하 테스트 시나리오 업데이트 | open | 정적/상태 경로 부하 테스트 가능 |
| C-004 | P2 | 모델 학습 잡 분리 초안 | open | 수집/예측과 독립 실행 가능 |
| C-005 | P1 | pipeline worker 역할 분리 | done (2026-02-17) | `WORKER_EXECUTION_ROLE` + `WORKER_PUBLISH_MODE`로 ingest/predict/export 실행 경계를 분리했고, 전용 엔트리포인트(`worker_ingest.py`, `worker_predict.py`, `worker_export.py`)를 추가했다. 운영 기본은 compose 2-service(`worker-ingest`,`worker-publish`)이며, publish는 ingest watermark gate를 통해 신규 데이터 감지 시에만 predict/export를 수행한다. base ingest(`1m`,`1h`)와 derived materialization(`1d/1w/1M`) 경계는 `run_ingest_step` 라우팅으로 코드 레벨 고정된다. 도메인 로직은 `workers/ingest.py`, `workers/predict.py`, `workers/export.py`로 분리되어 `pipeline_worker.py`는 orchestrator/runtime glue 중심으로 유지한다 |
| C-006 | P1 | timeframe 경계 기반 scheduler 전환 | done (2026-02-17) | `WORKER_SCHEDULER_MODE=boundary` 기준으로 UTC candle boundary에서 due timeframe만 실행되며, 경계 미도래 시 idle sleep으로 불필요 cycle을 억제한다. `runtime_metrics.json`에 `boundary_tracking.mode=boundary_scheduler`와 `missed_boundary_count/rate`가 기록된다 |
| C-007 | P1 | 신규 candle 감지 게이트 결합 | done (2026-02-17) | boundary 모드에서 `symbol+timeframe`별 detection gate가 `run/skip`를 분기하고(`new_closed_candle`/`no_new_closed_candle` 등), `runtime_metrics.json`에 `detection_gate_{run,skip}_counts/events`와 `missed_boundary_count/rate`가 함께 기록된다. 단위 회귀에서 경계 정상 시나리오 `missed_boundary=0`을 검증한다 |
| C-008 | P1 | `1h` underfill RCA + temporary guard sunset 결정 | done (2026-02-17) | legacy fallback 오염 경로(`timeframe` 미존재 row만 허용) 차단 + 회귀 테스트 반영 + `D-2026-02-17-37` 문서화 완료. guard 7일 관찰은 블로킹 조건이 아닌 운영 메모로 `C-002` 계측 트랙에서 병행 추적 |
| C-009 | P1 | monitor Influx-JSON consistency timeframe-aware 보강 | done (2026-02-19) | `scripts/status_monitor.py`의 Influx latest 조회가 `symbol+timeframe` 기준으로 분리되고, `PRIMARY_TIMEFRAME` legacy fallback을 유지하며, `tests/test_status_monitor.py` 회귀(신규 케이스 포함)와 전체 회귀 `108 passed`로 검증됨 |
| C-011 | P1 | boundary scheduler 재시작 catch-up 보강 | done (2026-02-19) | `initialize_boundary_schedule`가 현재 경계 기준으로 초기화되어 재시작 직후 `1d/1w/1M`이 다음 경계까지 정체되지 않고 첫 cycle에서 due 처리되며, `tests/test_pipeline_worker.py` 신규 회귀 + 전체 회귀 `109 passed`로 검증됨 |
| C-010 | P2 | orchestrator 가독성 정리(`pipeline_worker.py` 제어면 경계 단순화) | open | `scripts/pipeline_worker.py`의 cycle commit/state 저장 책임이 명확히 분리되고(ingest_state vs watermark commit 경계), 동작 변경 없이 인지부하를 줄였음을 회귀 테스트 + 코드 리뷰 체크리스트로 검증 |

### Phase D (Model Evolution)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| D-001 | P1 | 모델 인터페이스 정의(`fit/predict/save/load`) | open | 기존 모델 호환 인터페이스 경유 |
| D-002 | P1 | 모델 메타데이터/버전 스키마 정의 | open | 버전/학습시간/데이터 범위 기록 |
| D-003 | P1 | Shadow 추론 파이프라인 도입 | open | shadow 결과 생성, 사용자 서빙 미반영 |
| D-004 | P1 | Champion vs Shadow 평가 리포트 | open | 최소 1개 지표 일별 산출 |
| D-005 | P1 | 승격 게이트 정책 구현 | open | 게이트 미달 시 승격 차단 |
| D-006 | P2 | 자동 재학습 잡(수동 트리거) | open | 운영자 수동 재학습 가능 |
| D-007 | P2 | 자동 재학습 스케줄링 | open | 설정 기반 주기 재학습 가능 |
| D-008 | P2 | 모델 롤백 절차/코드 추가 | open | 이전 champion 복귀 가능 |
| D-009 | P2 | Drift 알림 연동 | open | 임계 초과 시 경고 발송 |
| D-010 | P1 | 장기 timeframe 최소 샘플 gate 구현 | open | 최소 샘플 미달 TF는 `insufficient_data`로 표시하고 예측 서빙 차단 |
| D-011 | P1 | Model Coverage Matrix + Fallback Resolver 구현 | open | 기본 `timeframe-shared`/조건부 `symbol+timeframe dedicated` 정책과 `dedicated -> shared -> insufficient_data` fallback 체인이 코드/메타데이터/테스트로 검증됨 |

## 3. Immediate Bundle
1. `B-005`
2. `C-010`
3. `B-008`

## 4. Operating Rules
1. Task 시작 시 Assignee/ETA/Risk를 기록한다.
2. 완료 시 검증 증거(테스트/런타임)를 남긴다.
3. 실패/보류 시 원인과 재개 조건을 기록한다.
4. 새 부채 발견 시 `TECH_DEBT_REGISTER` 동기화가 완료 조건이다.

## 5. Archive Notes
1. A-011 세부 태스크 원문은 Archive 참고.
2. A-010 세부 태스크 원문은 Archive 참고.
3. 전체 작업 이력(변경 파일 리스트)은 Archive 참고.

## 6. R-002 Task Design Cards (B/C/D)
### Phase B
| ID | Why Now | Failure Mode | Verification | Rollback |
|---|---|---|---|---|
| B-001 | 1m/장기 TF를 동일 규칙으로 처리하면 지연/저표본/저장소 리스크를 동시에 키움 | 1m 예측 오버런, 장기 TF 저품질 예측, 보존 정책 충돌, 부분 이력 심볼 조기 노출에 따른 사용자 오판 | 정책 매트릭스 리뷰 + 설정 스키마 테스트 + `latest=180`/`14d+30d`/Hard Gate 규칙 dry-run + `internal`/`external` mismatch taxonomy 검증 + symbol activation gate(`hidden_backfilling`) 검증 | Phase A `1h` 단일 모드로 회귀 |
| B-002 | 파일 네이밍 불일치가 API/monitor 오탐(`missing`)을 유발함 | 잘못된 파일 탐색으로 상태 오판 및 경보 노이즈 | 파일명 규칙 테스트 + legacy fallback 동작 확인 | dual-read(신규+legacy) 유지 후 단계적 전환 |
| B-003 | export가 timeframe-aware가 아니면 산출물이 덮어써지고, 1m 예측 비서빙 정책 위반 위험이 생김 | 타임프레임 간 파일 충돌/유실 + 1m prediction 파일 노출 | 다중 timeframe 동시 export 테스트 + `1m` prediction 미생성 검증 | `1h` export 경로로 임시 복귀 |
| B-004 | manifest 부재 시 운영자가 전체 상태를 빠르게 파악하기 어려움 | manifest stale/오류로 잘못된 운영 판단 | manifest와 원본 파일 간 일관성 검사 + updated_at 검증 | manifest 소비 중지, 개별 파일 점검으로 회귀 |
| B-007 | 다중 timeframe 전환 후 운영자가 상태를 단일 화면에서 파악하기 어려움 | timeframe별 stale/degraded를 놓쳐 운영 대응 지연 | admin 뷰에서 symbol/timeframe 필터 + 상태 매트릭스 + updated_at 지연 표시 검증 | 기존 단일 timeframe 대시보드로 임시 회귀 |
| B-008 | FE가 manifest visibility를 소비하지 않으면 정책상 비노출 심볼이 사용자에게 노출될 수 있음 | backfilling 심볼 조기 노출로 사용자 신뢰 저하/해석 오류 발생 | FE 심볼 목록 필터 테스트(`hidden_backfilling` 제외) + ready 전환 시 노출 복귀 E2E 확인 | FE에서 visibility 필터 비활성화 후 기존 수동 심볼 목록으로 임시 회귀 |
| B-006 | Free Tier 50GB 제약에서 다중 심볼 1m 원본 장기 보관은 운영 중단 리스크를 만든다 | 디스크 고갈로 쓰기 실패, DB 성능 저하, 복구 지연 | 디스크 사용량 추세 검증 + `14d default / 30d cap` enforcement 테스트 + downsample 결과 무결성 검증 | retention/downsample 중지 후 기존 수집 정책으로 회귀 |
| B-005 | fallback endpoint를 무기한 유지하면 경계 혼선/숨은 의존이 누적됨 | 제거 시 숨어있던 호출 경로 장애 발생 | sunset 체크리스트 + fallback 비의존 운영 1 cycle 검증 | endpoint 복구 절차 즉시 실행(runbook) |

### Phase C
| ID | Why Now | Failure Mode | Verification | Rollback |
|---|---|---|---|---|
| C-001 | 심볼 확장 시 수동 코드 수정은 운영 실수를 키움 | 잘못된 심볼/시장 설정으로 워커 실패 확대 | 심볼 검증 로직 + canary 심볼 추가 검증 | 정적 allowlist로 즉시 회귀 |
| C-002 | C-005/C-006/C-007 의사결정을 위한 관측 근거가 현재 부족함 | 지표 부정확/과다로 잘못된 최적화 결정을 유도 | 실행시간/실패율/오버런 샘플 수집 + 오버헤드 측정 | 추가 메트릭 수집 비활성화 |
| C-003 | 부하 테스트 시나리오가 현재 경로(SSG/status) 현실을 충분히 반영하지 못함 | 비현실 시나리오로 거짓 안정성 확보 | baseline/stress 시나리오 재현성 검증 | 기존 시나리오로 임시 복귀 |
| C-004 | 학습 잡 미분리 상태가 운영 경로 자원 경합 위험을 높임 | 학습이 수집/예측 주기를 방해 | 학습 단독 실행 및 운영 경로 영향도 측정 | 수동 오프라인 학습 경로 유지 |
| C-005 | 단일 worker 결합 구조가 단계 장애를 전체 파이프라인으로 전파함 | 단계 간 계약 불일치로 freshness 저하/장애 확대, 파생 TF direct ingest 우회 경로 잔존 | 단계별 헬스체크 + 장애 격리 회귀 테스트 + `1d/1w/1M` direct exchange fetch 미호출 계약 테스트 | 단일 worker 엔트리포인트로 복귀 |
| C-006 | 고정 poll 루프는 경계 미스/불필요 cycle로 비용과 오탐을 증가시킴 | 경계 누락 또는 중복 트리거로 stale/중복 실행 발생 | UTC 경계 시뮬레이션 + timeframe별 실행 cadence 검증 | 기존 고정 poll 루프로 복귀 |
| C-007 | boundary-only는 신규 데이터가 없을 때도 불필요 cycle을 수행한다 | 신규 candle 감지 오탐/누락으로 skip 오류 또는 처리 지연 발생 | 신규 closed candle 감지 기반 run/skip 테스트 + `missed_boundary=0` 검증 | detection gate 비활성화 후 boundary-only 모드 유지 |
| C-008 | `1h` underfill이 재발하면 이후 C-006/C-005 결과 해석이 왜곡될 수 있음 | 임시 guard에 의존한 채 근본 원인 미확정 상태가 장기화됨 | RCA 증거(재현/로그/쿼리) + guard 트리거 추적 + 유지/제거 회귀 테스트 | guard를 유지한 채 RCA 후속 태스크로 분리 |
| C-010 | orchestrator에 제어면/호환 래퍼/상태 커밋 책임이 밀집돼 변경 시 인지부하가 높다 | 작은 수정도 영향 범위 예측 실패로 회귀 위험이 증가한다 | commit 경계 단위 테스트 + 회귀(`pytest`) + 리뷰 체크리스트(책임 분리/동작 불변) 통과 | 구조 정리만 되돌리고 기존 단일 흐름으로 복귀 |

### Phase D
| ID | Why Now | Failure Mode | Verification | Rollback |
|---|---|---|---|---|
| D-001 | 모델 교체/비교 자동화를 위해 공통 인터페이스가 선행돼야 함 | adapter 불일치로 기존 Prophet 경로 깨짐 | 계약 테스트(`fit/predict/save/load`) + 기존 모델 호환성 확인 | direct Prophet 호출 경로 유지 |
| D-002 | 메타데이터 부재 시 모델 provenance/비교/복구가 불가능함 | 스키마 드리프트로 로더 호환성 깨짐 | 스키마 검증 + backward compatibility 테스트 | 메타 필드 optional 읽기 모드로 복귀 |
| D-003 | shadow 경로 없이는 champion 교체 근거가 부족함 | shadow가 사용자 서빙 경로에 영향 | shadow 산출물 분리 저장 + 사용자 API 불변 확인 | shadow 실행 비활성화 |
| D-004 | 정량 비교 리포트 없이는 승격 기준이 주관적으로 흐름 | 지표 산식/기간 오류로 잘못된 판단 | 고정 샘플 데이터로 지표 계산 검증 | 리포트 기반 자동 판단 중지, 수동 리뷰 유지 |
| D-005 | 승격 게이트가 없으면 성능 저하 모델이 바로 반영될 위험 | 임계값 오설정으로 과잉 차단/과소 차단 | gate pass/fail 경계 테스트 + 롤백 시나리오 검증 | 수동 승격 정책으로 임시 회귀 |
| D-006 | 수동 재학습 트리거가 없으면 운영 대응 속도가 낮음 | 중복 실행/동시 실행으로 자원 고갈 | 실행 잠금(idempotency) + 중복 트리거 테스트 | 트리거 비활성화 후 수동 스크립트 실행 |
| D-007 | 스케줄 재학습은 수동 운영 한계를 줄이지만 겹침 위험이 큼 | 스케줄 중첩으로 운영 경로 성능 저하 | no-overlap 보장 검증 + 실행 시간 모니터링 | 스케줄 중지 후 D-006 수동 모드 회귀 |
| D-008 | 롤백 절차 없이는 모델 배포 실패 시 MTTR이 급증 | 잘못된 버전 복귀로 상태 악화 | 버전 pin 기반 롤백 리허설 + post-rollback smoke | 이전 champion 고정 포인터로 즉시 복귀 |
| D-009 | drift 탐지 없이는 성능 저하를 늦게 인지함 | 과도한 false alert로 운영 피로 증가 | 임계값 backtest + 경보 빈도 검증 | 경고 채널 격하 또는 알림 비활성화 |
| D-010 | 장기 TF에서 샘플 수가 부족하면 모델 비교/승격 판단이 왜곡된다 | 통계적으로 무의미한 지표로 잘못된 모델 선택 | timeframe별 최소 샘플 회귀 테스트 + 미달 시 `insufficient_data` 노출 테스트 | 장기 TF 예측 기능 비활성화 후 baseline 모델만 유지 |
| D-011 | 전 심볼/TF 전용 모델 일괄 도입은 비용/운영 복잡도를 급격히 증가시킨다 | 자원 고갈, 승격/롤백 불명확, 실패 은닉 fallback 발생 | coverage matrix 테스트 + 승격 게이트 테스트 + fallback 우선순위 테스트 | shared-only 모드로 즉시 회귀(dedicated 해제) |

## 7. R-003 Priority Reorder (Options + Adopted Baseline)
| Option | Intent | Ordered Sequence | 장점 | 리스크 |
|---|---|---|---|---|
| Option A (Adopted) | Stability-first, phase boundary 보호 | `R-004 -> B-001 -> B-002 -> B-003 -> B-004 -> B-006 -> C-002 -> C-008 -> C-006 -> C-007 -> C-005 -> R-005 -> B-007(P2) -> B-005(P2) -> D-001+` | 정책/저장소/서빙 경계를 먼저 고정해 C/D 재작업 가능성을 줄임 | 비용 최적화(C-006/C-007) 체감이 늦어질 수 있음 |
| Option B | Cost-first, C 조기 최적화 | `R-004 -> C-002 -> C-006 -> C-007 -> C-005 -> B-001 -> B-002 -> B-003 -> B-004 -> B-006 -> R-005 -> B-007(P2) -> B-005(P2) -> D-001+` | 루프 비용 절감 효과를 빠르게 확인 가능 | B 경계 미고정 상태에서 C 변경이 들어가 계약 드리프트/재작업 위험 증가 |

채택 기준선:
1. 현재 우선순위(`Stability > Cost > Performance`)에 따라 Option A를 기준선으로 채택한다.
2. `B-005`는 사용자 의견에 따라 P2를 유지한다.
3. Option B는 `C-002`에서 비용 압력이 즉시 심각하다는 증거가 나올 때 fallback 후보로만 유지한다.
4. `D-2026-02-13-33`/`D-2026-02-13-35`/`D-2026-02-17-36`/`D-2026-02-17-37`/`D-2026-02-19-41` 반영 후 활성 실행 순서는 `B-005(P2) -> C-010(P2) -> B-008(P2)`다.

## 8. R-004 Kickoff Contract (Accepted)
1. Kickoff 구현 묶음은 `B-002`, `B-003` 2개로 고정한다.
2. 단, `B-001` 정책 매트릭스 잠금이 선행되지 않으면 `B-002`/`B-003` 구현 착수는 보류한다.
3. 실행 순서는 `B-001` 선행 잠금 이후 `B-002` 선행, `B-003` 후행으로 고정한다.
4. `B-002` 검증 경계는 파일명 규칙 단위 테스트(`{symbol}_{timeframe}`) 통과와 legacy fallback 유지 시 상태 오판(`missing`) 비증가다.
5. `B-002` 롤백 경계는 신규 파일명 읽기를 비활성화하고 legacy 파일명 읽기만 강제하는 것이다(dual-read에서 legacy 우선으로 회귀).
6. `B-003` 검증 경계는 다중 timeframe 동시 export 시 파일 충돌/덮어쓰기 부재와 산출물 필수 필드/`updated_at`/timeframe 구분 값 일관성, 그리고 `1m` prediction 비생성 정책 준수다.
7. `B-003` 롤백 경계는 timeframe-aware export를 중지하고 `1h` 단일 export 경로로 즉시 복귀하는 것이다.
8. `C-005`, `C-006`, `C-007`은 `B-003` 검증 증거 확보 전에는 구현 착수를 보류한다.
9. 위 보류 조건은 `B-003` 완료(2026-02-13)로 충족되었다.
