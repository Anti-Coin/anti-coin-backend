# Coin Predict Task Board (Active)

- Last Updated: 2026-02-21
- Rule: 활성 태스크만 유지하고, 완료 상세 이력은 Archive로 분리
- Full Phase A History: `docs/archive/phase_a/TASKS_MINIMUM_UNITS_PHASE_A_FULL_2026-02-12.md`
- Full Phase B History: `docs/archive/phase_b/TASKS_MINIMUM_UNITS_PHASE_B_FULL_2026-02-19.md`
- Full Phase C History: `docs/archive/phase_c/TASKS_MINIMUM_UNITS_PHASE_C_FULL_2026-02-20.md`

## 0. Priority
1. P0: 안정성/무결성 즉시 영향
2. P1: 확장성/운영성 핵심 영향
3. P2: 품질/가독성/자동화 개선

## 1. Milestone Snapshot
1. Phase A(Reliability Baseline) 완료 (2026-02-12)
2. Phase B(Timeframe Expansion) 완료 (2026-02-19)
3. Phase C(Scale and Ops) 완료 (2026-02-20)
4. `R-005` 완료 (2026-02-19): SLA-lite baseline을 user plane availability 중심으로 고정
5. `C-004` 완료 (2026-02-20): 학습 one-shot 실행 경계(`worker-train`) 잠금
6. 현재 활성 구현 트랙은 Phase D(Model Evolution)이다.

## 2. Active Tasks
### Rebaseline (Post-Phase A)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| R-001 | P0 | B/C/D Phase 목적 및 Exit 조건 재검증 | done (2026-02-12) | B/C/D Objective/Exit 재정의가 `docs/PLAN_LIVING_HYBRID.md`에 반영됨 |
| R-002 | P0 | B/C/D 태스크 재세분화(리스크 반영) | done (2026-02-12) | 활성 태스크별 `why/failure/verify/rollback` 설계 카드가 정렬됨 |
| R-003 | P0 | 교차 Phase 의존성/우선순위 재정렬 | done (2026-02-12) | Option A/B 비교 및 채택 기준선 확정 |
| R-004 | P1 | Phase B kickoff 구현 묶음 확정 | done (2026-02-12) | `B-002 -> B-003` kickoff 묶음과 검증/롤백 경계 확정 |
| R-005 | P1 | SLA-lite 지표 baseline 정의 | done (2026-02-19) | availability/alert miss/MTTR-stale 공식/데이터 소스/산출 주기 잠금 |

### Phase B (Timeframe Expansion) - Summary
| ID | Priority | Task | Status |
|---|---|---|---|
| B-001 | P1 | timeframe tier 정책 매트릭스 확정(수집/보존/서빙/예측) | done (2026-02-17) |
| B-002 | P1 | 파일 네이밍 규칙 통일 | done (2026-02-13) |
| B-003 | P1 | history/prediction export timeframe-aware 전환 | done (2026-02-13) |
| B-004 | P1 | manifest 파일 생성 | done (2026-02-13) |
| B-005 | P2 | `/history`/`/predict` fallback 정리(sunset) | done (2026-02-19) |
| B-006 | P1 | 저장소 예산 가드(50GB) + retention/downsample 실행 | done (2026-02-13) |
| B-007 | P2 | 운영 대시보드(admin) timeframe 확장 | done (2026-02-19) |
| B-008 | P2 | FE 심볼 노출 게이트 연동(`hidden_backfilling`) | done (2026-02-19, sunset scope close) |

### Phase C (Scale and Ops) - Summary
| ID | Priority | Task | Status |
|---|---|---|---|
| C-001 | P1 | 심볼 목록 확장 자동화 | done (2026-02-20) |
| C-002 | P1 | 실행시간/실패율 메트릭 수집 | done (2026-02-17) |
| C-003 | P2 | 부하 테스트 시나리오 업데이트 | done (2026-02-20) |
| C-004 | P2 | 모델 학습 잡 분리 초안 | done (2026-02-20) |
| C-005 | P1 | pipeline worker 역할 분리 | done (2026-02-17) |
| C-006 | P1 | timeframe 경계 기반 scheduler 전환 | done (2026-02-17) |
| C-007 | P1 | 신규 candle 감지 게이트 결합 | done (2026-02-17) |
| C-008 | P1 | `1h` underfill RCA + temporary guard sunset 결정 | done (2026-02-17) |
| C-009 | P1 | monitor Influx-JSON consistency timeframe-aware 보강 | done (2026-02-19) |
| C-010 | P2 | orchestrator 가독성 정리(`pipeline_worker.py` 제어면 경계 단순화) | done (2026-02-19) |
| C-011 | P1 | boundary scheduler 재시작 catch-up 보강 | done (2026-02-19) |
| C-012 | P2 | 디렉토리/파일 재배치 계약 정리 | done (2026-02-20) |
| C-013 | P2 | `pipeline_worker.py` 저수준 가독성 분해(timeboxed) | done (2026-02-20) |
| C-014 | P1 | derived TF skip 경로 publish starvation 완화 | done (2026-02-20) |
| C-015 | P1 | prediction status fallback 경계 강화 | done (2026-02-20) |
| C-016 | P2 | stale 장기 지속 재시도/승격 정책 정비 | done (2026-02-20) |

### Phase D (Model Evolution) - Active
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
| D-011 | P1 | Model Coverage Matrix + Fallback Resolver 구현 | open | `dedicated -> shared -> insufficient_data` fallback 체인이 코드/메타데이터/테스트로 검증됨 |
| D-012 | P1 | 학습 데이터 SoT 정렬(Influx 기반 closed-candle snapshot) | open | 학습 입력이 Influx SoT 기준으로 고정되고 직접 exchange fetch 경로가 학습 코드에서 제거됨 |
| D-013 | P1 | 재학습 트리거 정책 정의(시간+이벤트) | open | 재학습 trigger matrix(시간 주기, candle 누적, 드리프트 신호)와 cooldown 정책이 문서/코드로 고정됨 |
| D-014 | P1 | 학습 실행 no-overlap/락 가드 | open | 학습 동시 실행 차단, stale lock 복구 규칙, 회귀 테스트가 고정됨 |
| D-015 | P2 | 학습 실행 관측성/알림 baseline | open | 학습 실행시간/성공-실패/최근성 메트릭과 장애 알림 기준이 운영 문서와 함께 반영됨 |
| D-016 | P2 | `pipeline_worker.py` 상태 관리 분리(`worker_state.py`) | open | watermark/prediction_health/symbol_activation/downsample_lineage/runtime_metrics load/save/upsert가 `scripts/worker_state.py`로 이동, 회귀 테스트 통과 |
| D-017 | P2 | `pipeline_worker.py` `_ctx()` 래퍼 패턴 해소 | open | 테스트가 `workers.*` 직접 참조로 전환되고 `_ctx()` 래퍼 함수 ~30개가 제거됨, 회귀 테스트 통과 |

## 3. Immediate Bundle
1. `D-001`
2. `D-002`
3. `D-012`

## 4. Operating Rules
1. Task 시작 시 Assignee/ETA/Risk를 기록한다.
2. 완료 시 검증 증거(테스트/런타임)를 남긴다.
3. 실패/보류 시 원인과 재개 조건을 기록한다.
4. 새 부채 발견 시 `TECH_DEBT_REGISTER` 동기화가 완료 조건이다.

## 5. Archive Notes
1. Phase A 상세 원문은 `docs/archive/phase_a/*`에서 확인한다.
2. Phase B 상세 원문은 `docs/archive/phase_b/*`에서 확인한다.
3. Phase C 상세 원문은 `docs/archive/phase_c/*`에서 확인한다.
4. 활성 문서에는 현재 실행 규칙만 유지한다.

## 6. Phase C Archive Contract
1. Phase C 설계 카드/세부 Done Condition/리스크 비교표는 `docs/archive/phase_c/TASKS_MINIMUM_UNITS_PHASE_C_FULL_2026-02-20.md`를 단일 출처로 사용한다.
2. Phase C를 재개할 경우, 새 태스크 ID를 부여하고 본 문서 Active 섹션으로 다시 승격한다.
