# Coin Predict Task Board (Active)

- Last Updated: 2026-02-19
- Rule: 활성 태스크만 유지하고, 완료 상세 이력은 Archive로 분리
- Full Phase A History: `docs/archive/phase_a/TASKS_MINIMUM_UNITS_PHASE_A_FULL_2026-02-12.md`
- Full Phase B History: `docs/archive/phase_b/TASKS_MINIMUM_UNITS_PHASE_B_FULL_2026-02-19.md`

## 0. Priority
1. P0: 안정성/무결성 즉시 영향
2. P1: 확장성/운영성 핵심 영향
3. P2: 품질/가독성/자동화 개선

## 1. Milestone Snapshot
1. Phase A(Reliability Baseline) 완료 (2026-02-12)
2. Phase B(Timeframe Expansion) 완료 (2026-02-19)
3. `R-005` 완료 (2026-02-19): SLA-lite baseline을 user plane availability 중심으로 고정
4. `B-007` 완료 (2026-02-19): admin 대시보드 manifest-first 전환 및 회귀 검증 완료
5. `B-005` 완료 (2026-02-19): `/history`/`/predict` sunset(`410`) + 오너 확인 기반 fallback 비의존 운영 확인
6. `B-008` 완료 (2026-02-19, sunset scope close): FE 미구축 상태에서 종료, FE 재개 시 재오픈 조건으로 전환

## 2. Active Tasks
### Rebaseline (Post-Phase A)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| R-001 | P0 | B/C/D Phase 목적 및 Exit 조건 재검증 | done (2026-02-12) | B/C/D Objective/Exit 재정의가 `docs/PLAN_LIVING_HYBRID.md`에 반영됨 |
| R-002 | P0 | B/C/D 태스크 재세분화(리스크 반영) | done (2026-02-12) | 활성 태스크별 `why/failure/verify/rollback` 설계 카드가 본 문서 Section 6에 반영됨 |
| R-003 | P0 | 교차 Phase 의존성/우선순위 재정렬 | done (2026-02-12) | Option A/B 비교 및 채택 기준선이 본 문서 Section 7에 반영됨 |
| R-004 | P1 | Phase B kickoff 구현 묶음 확정 | done (2026-02-12) | `B-002 -> B-003` kickoff 묶음과 검증/롤백 경계가 본 문서 Section 8에 반영됨 |
| R-005 | P1 | SLA-lite 지표 baseline 정의 | done (2026-02-19) | availability/alert miss/MTTR-stale 공식/데이터 소스/산출 주기가 user plane 기준으로 고정됨 |

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

### Phase C (Scale and Ops)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| C-001 | P1 | 심볼 목록 확장 자동화 | open | 심볼 추가 시 코드 수정 최소화 |
| C-002 | P1 | 실행시간/실패율 메트릭 수집 | done (2026-02-17) | `static_data/runtime_metrics.json`에 cycle 실행시간/실패율/overrun 추세 누적 + `ingest_since_source_counts`/`rebootstrap_events`/`underfill_guard_retrigger_*` 집계 제공 |
| C-003 | P2 | 부하 테스트 시나리오 업데이트 | open | 정적/상태 경로 부하 테스트 가능 |
| C-004 | P2 | 모델 학습 잡 분리 초안 | open | 수집/예측과 독립 실행 가능 |
| C-005 | P1 | pipeline worker 역할 분리 | done (2026-02-17) | `WORKER_EXECUTION_ROLE` + `WORKER_PUBLISH_MODE` 분리, compose 2-service(`worker-ingest`,`worker-publish`) 전환, 도메인 로직 `workers/*` 분리 |
| C-006 | P1 | timeframe 경계 기반 scheduler 전환 | done (2026-02-17) | `WORKER_SCHEDULER_MODE=boundary` 기준으로 due timeframe만 실행, `missed_boundary_count/rate` 계측 |
| C-007 | P1 | 신규 candle 감지 게이트 결합 | done (2026-02-17) | `detection_gate_{run,skip}` 집계 반영 + 경계 정상 시나리오 `missed_boundary=0` 회귀 검증 |
| C-008 | P1 | `1h` underfill RCA + temporary guard sunset 결정 | done (2026-02-17) | legacy fallback 오염 경로 차단(`not exists r["timeframe"]`) + 회귀/문서화 완료 |
| C-009 | P1 | monitor Influx-JSON consistency timeframe-aware 보강 | done (2026-02-19) | Influx latest 조회를 `symbol+timeframe` 기준으로 고정 + `PRIMARY_TIMEFRAME` legacy fallback 유지 |
| C-011 | P1 | boundary scheduler 재시작 catch-up 보강 | done (2026-02-19) | 재시작 직후 `1d/1w/1M` missed boundary를 첫 cycle에서 따라잡도록 초기화 경계 조정 |
| C-010 | P2 | orchestrator 가독성 정리(`pipeline_worker.py` 제어면 경계 단순화) | open | cycle commit/state 저장 책임(ingest_state vs watermark commit) 분리 + 동작 불변 회귀 검증 |

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
| D-011 | P1 | Model Coverage Matrix + Fallback Resolver 구현 | open | `dedicated -> shared -> insufficient_data` fallback 체인이 코드/메타데이터/테스트로 검증됨 |

## 3. Immediate Bundle
1. `C-010`
2. `C-001`
3. `C-003`

## 4. Operating Rules
1. Task 시작 시 Assignee/ETA/Risk를 기록한다.
2. 완료 시 검증 증거(테스트/런타임)를 남긴다.
3. 실패/보류 시 원인과 재개 조건을 기록한다.
4. 새 부채 발견 시 `TECH_DEBT_REGISTER` 동기화가 완료 조건이다.

## 5. Archive Notes
1. Phase A 상세 원문은 `docs/archive/phase_a/*`에서 확인한다.
2. Phase B 상세 원문은 `docs/archive/phase_b/*`에서 확인한다.
3. 활성 문서에는 현재 실행 규칙만 유지한다.

## 6. R-002 Task Design Cards (Phase C/D)
### Phase C
| ID | Why Now | Failure Mode | Verification | Rollback |
|---|---|---|---|---|
| C-001 | 심볼 확장 시 수동 코드 수정은 운영 실수를 키움 | 잘못된 심볼/시장 설정으로 워커 실패 확대 | 심볼 검증 로직 + canary 심볼 추가 검증 | 정적 allowlist로 즉시 회귀 |
| C-002 | C-005/C-006/C-007 의사결정을 위한 관측 근거가 현재 부족함 | 지표 부정확/과다로 잘못된 최적화 결정을 유도 | 실행시간/실패율/오버런 샘플 수집 + 오버헤드 측정 | 추가 메트릭 수집 비활성화 |
| C-003 | 부하 테스트 시나리오가 현재 경로(SSG/status) 현실을 충분히 반영하지 못함 | 비현실 시나리오로 거짓 안정성 확보 | baseline/stress 시나리오 재현성 검증 | 기존 시나리오로 임시 복귀 |
| C-004 | 학습 잡 미분리 상태가 운영 경로 자원 경합 위험을 높임 | 학습이 수집/예측 주기를 방해 | 학습 단독 실행 및 운영 경로 영향도 측정 | 수동 오프라인 학습 경로 유지 |
| C-005 | 단일 worker 결합 구조가 단계 장애를 전체 파이프라인으로 전파함 | 단계 간 계약 불일치로 freshness 저하/장애 확대 | 단계별 헬스체크 + 장애 격리 회귀 테스트 | 단일 worker 엔트리포인트로 복귀 |
| C-006 | 고정 poll 루프는 경계 미스/불필요 cycle로 비용과 오탐을 증가시킴 | 경계 누락 또는 중복 트리거로 stale/중복 실행 발생 | UTC 경계 시뮬레이션 + timeframe별 실행 cadence 검증 | 기존 고정 poll 루프로 복귀 |
| C-007 | boundary-only는 신규 데이터가 없을 때도 불필요 cycle을 수행한다 | 신규 candle 감지 오탐/누락으로 skip 오류 또는 처리 지연 발생 | 신규 closed candle 감지 기반 run/skip 테스트 + `missed_boundary=0` 검증 | detection gate 비활성화 후 boundary-only 모드 유지 |
| C-008 | `1h` underfill이 재발하면 이후 C-006/C-005 결과 해석이 왜곡될 수 있음 | 임시 guard에 의존한 채 근본 원인 미확정 상태가 장기화됨 | RCA 증거 + guard 트리거 추적 + 유지/제거 회귀 테스트 | guard를 유지한 채 RCA 후속 태스크로 분리 |
| C-010 | orchestrator에 제어면/호환 래퍼/상태 커밋 책임이 밀집돼 변경 시 인지부하가 높다 | 작은 수정도 영향 범위 예측 실패로 회귀 위험이 증가한다 | commit 경계 단위 테스트 + 회귀(`pytest`) + 리뷰 체크리스트 통과 | 구조 정리만 되돌리고 기존 단일 흐름으로 복귀 |

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
| D-011 | 전 심볼/TF 전용 모델 일괄 도입은 비용/운영 복잡도를 급격히 증가시킨다 | 자원 고갈, 승격/롤백 불명확, 실패 은닉 fallback 발생 | coverage matrix 테스트 + 승격 게이트 테스트 + fallback 우선순위 테스트 | shared-only 모드로 즉시 회귀 |

## 7. R-003 Priority Reorder (Options + Adopted Baseline)
| Option | Intent | Ordered Sequence | 장점 | 리스크 |
|---|---|---|---|---|
| Option A (Adopted) | Stability-first, phase boundary 보호 | `R-004 -> B-001 -> B-002 -> B-003 -> B-004 -> B-006 -> C-002 -> C-008 -> C-006 -> C-007 -> C-005 -> R-005 -> B-007(P2) -> B-005(P2) -> D-001+` | 정책/저장소/서빙 경계를 먼저 고정해 C/D 재작업 가능성을 줄임 | 비용 최적화(C-006/C-007) 체감이 늦어질 수 있음 |
| Option B | Cost-first, C 조기 최적화 | `R-004 -> C-002 -> C-006 -> C-007 -> C-005 -> B-001 -> B-002 -> B-003 -> B-004 -> B-006 -> R-005 -> B-007(P2) -> B-005(P2) -> D-001+` | 루프 비용 절감 효과를 빠르게 확인 가능 | B 경계 미고정 상태에서 C 변경이 들어가 계약 드리프트/재작업 위험 증가 |

채택 기준선:
1. 현재 우선순위(`Stability > Cost > Performance`)에 따라 Option A를 기준선으로 채택한다.
2. `B-005`는 사용자 의견에 따라 P2를 유지했다.
3. Option B는 `C-002`에서 비용 압력이 즉시 심각하다는 증거가 나올 때 fallback 후보로만 유지한다.
4. Phase B 종료 이후 활성 실행 순서는 `C-010 -> C-001 -> C-003`이다.

## 8. R-004 Kickoff Contract (Accepted)
1. Kickoff 구현 묶음은 `B-002`, `B-003` 2개로 고정했다.
2. `B-001` 정책 매트릭스 잠금이 선행되지 않으면 `B-002`/`B-003` 구현 착수는 보류했다.
3. 실행 순서는 `B-001` 선행 잠금 이후 `B-002` 선행, `B-003` 후행으로 고정했다.
4. `B-002` 롤백 경계는 legacy 우선 read 회귀였다.
5. `B-003` 롤백 경계는 `1h` 단일 export 경로 복귀였다.
6. 본 계약은 Phase B 완료와 함께 historical contract로 유지한다.
