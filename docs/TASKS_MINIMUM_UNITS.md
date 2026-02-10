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
| A-001 | P0 | 설정 중앙화 (`symbols`, `timeframes`, freshness threshold) ✅ | `config` 모듈 | 완료 (2026-02-10): 공통 설정 모듈로 참조 경로 통합 |
| A-002 | P0 | ingest_state 스키마/저장소 도입 | state 저장 코드 + 기본 조회/갱신 함수 | `symbol+timeframe`별 커서 유지 확인 |
| A-003 | P0 | ccxt 백필 pagination 루프 구현 ✅ | fetch 함수 리팩터링 | 완료 (2026-02-10): 단발 호출 제거 및 페이지 수집 루프 적용 |
| A-004 | P0 | closed candle 경계 계산 유틸 추가 | 시간 경계 함수 | 미완료 캔들 수집 없음 |
| A-005 | P0 | gap detector 구현 | 누락 구간 계산 로직 | 테스트 케이스에서 gap 식별 성공 |
| A-006 | P0 | gap refill 잡 추가 | 복구 실행 함수 | gap 발생 후 복구 확인 |
| A-007 | P0 | 원자적 JSON 쓰기 도입 ✅ | 공통 writer 유틸 | 완료 (2026-02-10): static JSON 저장 경로에 atomic write 적용 |
| A-008 | P0 | freshness 분류 유틸 (`fresh/stale/hard_stale/corrupt`) ✅ | 공통 판정 함수 | 완료 (2026-02-10): `utils/freshness.py` 도입 및 분류 테스트 통과 |
| A-009 | P0 | status 엔드포인트에 상태 상세 반영 ✅ | API 응답 스키마 업데이트 | 완료 (2026-02-10): soft stale 경고, hard stale 차단, 예외 처리 보강 |
| A-010 | P1 | alerting 규칙 확장 (hard_stale/corrupt/missing/recovery) ✅ | 모니터 + 알림 분기 로직 | 완료 (2026-02-10): 별도 모니터 스크립트 + 상태전이 알림/테스트 반영 |
| A-011 | P1 | 기본 회귀 테스트 추가 🔄 | 단위/통합 테스트 | 진행중 (2026-02-10): 우선 단위 테스트부터 확대 |
| A-012 | P1 | 세션 정렬 문서 체계 구축 ✅ | identity/constraints/debt/handoff 문서 | 완료 (2026-02-10): 새 세션 bootstrap 가능한 문서 스택 구성 |
| A-013 | P1 | 예측 시작 시점 경계 기준 정렬 ✅ | 경계 계산 유틸 + worker 예측 로직 | 완료 (2026-02-10): timeframe 경계(UTC) 기준으로 예측 시작점 고정 |
| A-014 | P1 | Influx-JSON 일관성 점검 추가 | 불일치 감지 로직/알림 | Influx 최신 시각과 static JSON 시각 불일치 탐지 가능 |

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
1. A-004
2. A-005
3. A-006
4. A-011-6
5. A-011-7

## 6. 태스크 운용 규칙
1. Task 시작 전 `Assignee`, `ETA`, `Risk`를 기록한다.
2. Task 완료 시 실제 영향 파일 경로를 남긴다.
3. Task 실패/보류 시 원인과 다음 시도 조건을 한 줄로 기록한다.
4. 모델 관련 Task(D-xxx)는 품질 지표와 롤백 경로가 없으면 `Done` 처리하지 않는다.
5. 새 기술 부채 발견 시 `TECH_DEBT_REGISTER` 업데이트 없이는 완료 처리하지 않는다.

## 7. A-011 세부 태스크 (테스트 체계)
| ID | Priority | Task | 산출물 | Done 조건 |
|---|---|---|---|---|
| A-011-1 | P1 | 테스트 인프라 정리 (`pytest`, 공통 fixture) ✅ | `tests/` 기반 구조 | 완료 (2026-02-10): `pytest.ini` + 테스트 실행 경로 정리 |
| A-011-2 | P1 | 파일 I/O 테스트 (`atomic_write_json`) ✅ | 단위 테스트 | 완료 (2026-02-10): 권한/원자교체/실패 temp 정리 검증 |
| A-011-3 | P1 | Freshness 로직 테스트 ✅ | 단위 테스트 | 완료 (2026-02-10): 상태 분류/예외/미래시간 케이스 검증 |
| A-011-4 | P1 | Status API 에러처리 테스트 ✅ | 단위/경량 API 테스트 | 완료 (2026-02-10): 포맷 오류/손상/stale/hard_stale 회귀 고정 |
| A-011-5 | P2 | 설정 파서 테스트 (`config`) ✅ | 단위 테스트 | 완료 (2026-02-10): env 파싱 경계조건 검증 |
| A-011-6 | P2 | 워커 핵심 유틸 테스트(점진 도입) | 단위 테스트 | backfill/fetch 경계조건 1차 검증 |
| A-011-7 | P2 | CI 테스트 게이트 도입 | workflow 변경 | 테스트 실패 시 배포 단계 진입 금지 |

## 8. A-010 세부 태스크 (Alert Monitor)
| ID | Priority | Task | 산출물 | Done 조건 |
|---|---|---|---|---|
| A-010-1 | P1 | 알림 설계 고정 (이벤트/대상/중복억제) ✅ | 문서/결정 로그 | 완료 (2026-02-10): hard_stale/corrupt/missing/recovery 전이 규칙 확정 |
| A-010-2 | P1 | 별도 모니터 스크립트 구현 ✅ | `scripts/status_monitor.py` | 완료 (2026-02-10): static artifact 상태 주기 점검 구현 |
| A-010-3 | P1 | Discord 알림 연동 ✅ | webhook 전송 로직 | 완료 (2026-02-10): 이벤트 메시지 템플릿 + 전송 처리 |
| A-010-4 | P1 | 상태전이 테스트 ✅ | 단위 테스트 | 완료 (2026-02-10): 중복 억제/복구 알림 케이스 검증 |
| A-010-5 | P2 | 런타임 서비스 연결 ✅ | `docker-compose.yml` | 완료 (2026-02-10): monitor 서비스 추가 |
| A-010-6 | P1 | worker/monitor 실행 엔트리포인트 분리 ✅ | `docker/Dockerfile.worker` | 완료 (2026-02-10): worker 기본 CMD + 범용 ENTRYPOINT 전환 |

## 9. 작업 이력
1. 2026-02-10: A-001 완료
   변경 파일: `utils/config.py`, `scripts/pipeline_worker.py`, `scripts/train_model.py`, `api/main.py`, `admin/app.py`, `.env.example`
2. 2026-02-10: A-003 완료
   변경 파일: `scripts/pipeline_worker.py`
3. 2026-02-10: A-007 완료
   변경 파일: `utils/file_io.py`, `scripts/pipeline_worker.py`
4. 2026-02-10: A-011 시작
   변경 파일: `docs/PLAN_LIVING_HYBRID.md`, `docs/TASKS_MINIMUM_UNITS.md`, `docs/DECISIONS.md`, `docs/TEST_STRATEGY.md`
5. 2026-02-10: A-008 완료
   변경 파일: `utils/freshness.py`, `utils/config.py`, `api/main.py`, `.env.example`
6. 2026-02-10: A-009 완료
   변경 파일: `api/main.py`, `tests/test_api_status.py`
7. 2026-02-10: A-011-1~5 완료
   변경 파일: `pytest.ini`, `tests/test_file_io.py`, `tests/test_freshness.py`, `tests/test_api_status.py`, `tests/test_config.py`, `requirements.txt`
8. 2026-02-10: A-012 완료
   변경 파일: `docs/README.md`, `docs/PROJECT_IDENTITY.md`, `docs/ENGINEERING_CONSTITUTION.md`, `docs/OPERATING_CONSTRAINTS.md`, `docs/TECH_DEBT_REGISTER.md`, `docs/SESSION_HANDOFF.md`, `docs/GLOSSARY.md`, `docs/SESSION_BOOTSTRAP_PROMPT.md`, `.codex/STARTUP_PROTOCOL.md`, `.codex/CONTEXT.md`, `.codex/RULES.md`, `.codex/WORKFLOW.md`, `.codex/QUESTIONS.md`, `.codex/REPO_MAP.md`
9. 2026-02-10: A-010 시작
   변경 파일: `docs/TASKS_MINIMUM_UNITS.md`, `docs/PLAN_LIVING_HYBRID.md`, `docs/DECISIONS.md`, `docs/TECH_DEBT_REGISTER.md`, `docs/SESSION_HANDOFF.md`
10. 2026-02-10: A-010 완료
   변경 파일: `scripts/status_monitor.py`, `tests/test_status_monitor.py`, `docker-compose.yml`, `.env.example`, `docs/TASKS_MINIMUM_UNITS.md`
11. 2026-02-10: A-010 후속 패치 완료
   변경 파일: `docker/entrypoint_worker.sh`, `docker/Dockerfile.worker`, `docs/TASKS_MINIMUM_UNITS.md`, `docs/TECH_DEBT_REGISTER.md`, `docs/DECISIONS.md`, `docs/SESSION_HANDOFF.md`
12. 2026-02-10: A-013 완료
   변경 파일: `utils/time_alignment.py`, `scripts/pipeline_worker.py`, `tests/test_time_alignment.py`
13. 2026-02-10: 문서 갱신 정책/신뢰 소스 결정 반영
   변경 파일: `docs/DECISIONS.md`, `docs/PLAN_LIVING_HYBRID.md`, `docs/OPERATING_CONSTRAINTS.md`, `docs/TASKS_MINIMUM_UNITS.md`, `docs/TECH_DEBT_REGISTER.md`
