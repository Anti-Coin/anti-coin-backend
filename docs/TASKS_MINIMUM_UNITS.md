# Coin Predict Task Board (Active)

- Last Updated: 2026-02-12
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

## 2. Active Tasks
### Phase B (Timeframe Expansion)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| B-001 | P1 | timeframe별 수집 정책 테이블 추가 | open | 1m/1h/1d/1w/1M 정책 분리 |
| B-002 | P1 | 파일 네이밍 규칙 통일 | open | `{symbol}_{timeframe}` 규칙 적용 |
| B-003 | P1 | history/prediction export timeframe-aware 전환 | open | 다중 timeframe 파일 동시 생성 |
| B-004 | P1 | manifest 파일 생성 | open | 심볼/타임프레임별 최신 상태 요약 |
| B-005 | P2 | `/history`/`/predict` fallback 정리(sunset) | open | 사용자/운영 경로 경계 유지 상태로 정리 완료 |

### Phase C (Scale and Ops)
| ID | Priority | Task | Status | Done Condition |
|---|---|---|---|---|
| C-001 | P1 | 심볼 목록 확장 자동화 | open | 심볼 추가 시 코드 수정 최소화 |
| C-002 | P1 | 실행시간/실패율 메트릭 수집 | open | 주기별 성능 추세 확인 가능 |
| C-003 | P2 | 부하 테스트 시나리오 업데이트 | open | 정적/상태 경로 부하 테스트 가능 |
| C-004 | P2 | 모델 학습 잡 분리 초안 | open | 수집/예측과 독립 실행 가능 |
| C-005 | P1 | pipeline worker 역할 분리 | open | ingest 지연/장애가 predict/export에 즉시 전파되지 않음 |
| C-006 | P1 | timeframe 경계 기반 trigger 전환 | open | 불필요 cycle 감소 + 정합성 개선 |

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

## 3. Immediate Bundle
1. `C-005`
2. `C-006`
3. `B-005`

## 4. Operating Rules
1. Task 시작 시 Assignee/ETA/Risk를 기록한다.
2. 완료 시 검증 증거(테스트/런타임)를 남긴다.
3. 실패/보류 시 원인과 재개 조건을 기록한다.
4. 새 부채 발견 시 `TECH_DEBT_REGISTER` 동기화가 완료 조건이다.

## 5. Archive Notes
1. A-011 세부 태스크 원문은 Archive 참고.
2. A-010 세부 태스크 원문은 Archive 참고.
3. 전체 작업 이력(변경 파일 리스트)은 Archive 참고.
