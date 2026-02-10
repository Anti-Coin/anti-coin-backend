# Coin Predict 최소 단위 Task 보드

- Last Updated: 2026-02-10
- Rule: 각 Task는 독립 PR 단위로 완료 가능해야 한다.
- Rule: 하나의 Task는 하나의 핵심 결과물만 만든다.

## 0. 우선순위 정의
1. P0: 안정성/데이터 무결성에 즉시 영향
2. P1: 확장성/운영성에 높은 영향
3. P2: 품질 개선, 리팩터링, 가시성 강화

## 1. Phase A (Reliability Baseline) - 필수 선행
| ID | Priority | Task | 산출물 | Done 조건 |
|---|---|---|---|---|
| A-001 | P0 | 설정 중앙화 (`symbols`, `timeframes`, freshness threshold) | `config` 모듈 | 심볼/타임프레임/임계값을 1곳에서 수정 가능 |
| A-002 | P0 | ingest_state 스키마/저장소 도입 | state 저장 코드 + 기본 조회/갱신 함수 | `symbol+timeframe`별 커서 유지 확인 |
| A-003 | P0 | ccxt 백필 pagination 루프 구현 | fetch 함수 리팩터링 | `limit=1000` 단발 호출 제거 |
| A-004 | P0 | closed candle 경계 계산 유틸 추가 | 시간 경계 함수 | 미완료 캔들 수집 없음 |
| A-005 | P0 | gap detector 구현 | 누락 구간 계산 로직 | 테스트 케이스에서 gap 식별 성공 |
| A-006 | P0 | gap refill 잡 추가 | 복구 실행 함수 | gap 발생 후 복구 확인 |
| A-007 | P0 | 원자적 JSON 쓰기 도입 | 공통 writer 유틸 | 부분 파일/파손 파일 재현 실패 |
| A-008 | P0 | freshness 분류 유틸 (`fresh/stale/hard_stale/corrupt`) | 공통 판정 함수 | 샘플 입력별 상태 일치 |
| A-009 | P0 | status 엔드포인트에 상태 상세 반영 | API 응답 스키마 업데이트 | 상태값 + 경고 메시지 노출 |
| A-010 | P1 | alerting 규칙 확장 (hard_stale/corrupt 시 알림) | 알림 분기 로직 | 조건별 알림 전송 확인 |
| A-011 | P1 | 기본 회귀 테스트 추가 | 단위/통합 테스트 | 핵심 시나리오 CI 통과 |

## 2. Phase B (Timeframe Expansion) - A 완료 후
| ID | Priority | Task | 산출물 | Done 조건 |
|---|---|---|---|---|
| B-001 | P1 | timeframe별 수집 정책 테이블 추가 | 정책 딕셔너리 | 1m/1h/1d/1w/1M 정책 분리 |
| B-002 | P1 | 파일 네이밍 규칙 통일 | export 규칙 변경 | `{symbol}_{timeframe}` 규칙 적용 |
| B-003 | P1 | history/prediction export를 timeframe aware로 변경 | exporter 개선 | 다중 timeframe 파일 동시 생성 |
| B-004 | P1 | manifest 파일 생성 | `manifest.json` | 심볼/타임프레임별 최신 상태 요약 |
| B-005 | P2 | API fallback 정리 (`history/predict` 디버그 경로 명확화) | API 주석/문서/분기 | 운영 경로와 디버그 경로 구분 |

## 3. Phase C (Scale and Ops) - B 완료 후
| ID | Priority | Task | 산출물 | Done 조건 |
|---|---|---|---|---|
| C-001 | P1 | 심볼 목록 확장 자동화 | 심볼 설정/검증 로직 | 심볼 추가 시 코드 수정 최소화 |
| C-002 | P1 | 잡 실행시간/실패율 메트릭 수집 | 로그/메트릭 필드 추가 | 주기별 성능 추세 확인 가능 |
| C-003 | P2 | 부하 테스트 시나리오 업데이트 | `tests/locustfile.py` 개선 | 정적/상태 경로 부하 테스트 가능 |
| C-004 | P2 | 모델 학습 잡 분리 초안 | 학습 엔트리포인트 분리 | 수집/예측과 독립 실행 가능 |

## 4. Phase D (Model Evolution) - B 이후, C와 병행 가능
| ID | Priority | Task | 산출물 | Done 조건 |
|---|---|---|---|---|
| D-001 | P1 | 모델 인터페이스 정의 (`fit/predict/save/load`) | `BaseModel` 인터페이스 + Prophet 어댑터 | 기존 Prophet 동작 유지한 채 인터페이스 경유 가능 |
| D-002 | P1 | 모델 메타데이터/버전 스키마 정의 | 모델 메타 JSON 스키마 | 모델 파일에 버전/학습시간/데이터 범위 기록 |
| D-003 | P1 | Shadow 추론 파이프라인 도입 | Shadow 실행 코드 + 결과 저장 경로 | Shadow 결과 생성되지만 사용자 서빙엔 미반영 |
| D-004 | P1 | Champion vs Shadow 평가 리포트 | 비교 리포트 생성 코드 | 최소 1개 지표(MAPE 등) 일별 산출 가능 |
| D-005 | P1 | 승격 게이트 정책 구현 | 승격 조건 판정 로직 | 게이트 미달 시 승격 차단 확인 |
| D-006 | P2 | 자동 재학습 잡(수동 트리거) | retrain 엔트리포인트 | 운영자가 수동 재학습 실행 가능 |
| D-007 | P2 | 자동 재학습 스케줄링 | 스케줄 실행 로직 | 설정 기반 주기 재학습 가능 |
| D-008 | P2 | 모델 롤백 절차/코드 추가 | 롤백 실행 함수 + 문서 | 이전 champion으로 복귀 가능 |
| D-009 | P2 | Drift 알림 연동 | drift 감지 + alert 분기 | 임계 초과 시 경고 발송 |

## 5. 즉시 시작 권장 Task 묶음 (이번 사이클)
1. A-001
2. A-003
3. A-007
4. A-008
5. A-009

## 6. 태스크 운용 규칙
1. Task 시작 전 `Assignee`, `ETA`, `Risk`를 기록한다.
2. Task 완료 시 실제 영향 파일 경로를 남긴다.
3. Task 실패/보류 시 원인과 다음 시도 조건을 한 줄로 기록한다.
4. 모델 관련 Task(D-xxx)는 품질 지표와 롤백 경로가 없으면 `Done` 처리하지 않는다.
