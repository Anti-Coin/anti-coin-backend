# Coin Predict Technical Debt Register

- Last Updated: 2026-02-12
- Purpose: 기술 부채를 세션 간 누락 없이 추적

## 1. 운용 규칙
1. 코드 변경 후 새 부채가 생기면 즉시 항목을 추가한다.
2. 부채 해소 시 `status`를 `resolved`로 바꾸고 근거를 남긴다.
3. 정책/우선순위 변경은 `DECISIONS`와 함께 기록한다.

## 2. Debt List
| ID | Category | Debt | Risk | Status | Linked Task | Next Action |
|---|---|---|---|---|---|---|
| TD-001 | Ingest | closed candle 경계 미구현 | 미완료 캔들 저장 가능성 | resolved | A-004 | latest closed candle 경계 필터 적용 완료, 회귀 테스트 유지 |
| TD-002 | Ingest | gap detector 미구현 | 데이터 누락 장기화 가능 | resolved | A-005 | 누락 구간 식별 유틸/테스트 및 worker 경고 로그 적용 완료 |
| TD-003 | Ingest | gap refill 잡 미구현 | 누락 자동 복구 불가 | resolved | A-006 | 감지 gap 구간 재수집/병합 경로 구현 완료, 회귀 테스트 유지 |
| TD-004 | Alerting | hard_stale/corrupt/missing/recovery 알림 미연동 | 운영자 탐지 지연 | mitigated | A-010 | 배포 환경에서 monitor 서비스 기동/알림 확인 후 `resolved` 전환 |
| TD-005 | API | timeframe-aware 파일 네이밍 미완성 | 확장 시 라우팅 혼선 | open | B-002 | 파일명 규칙 통일 |
| TD-006 | API | manifest 미구현 | 상태 가시성 부족 | open | B-004 | manifest 생성 경로 추가 |
| TD-007 | Worker | 워커 경계 조건 테스트 부족 | 회귀 리스크 증가 | resolved | A-011-6 | pagination 종료 경계/리필 병합 경계 테스트 추가 완료 |
| TD-008 | CI/CD | 테스트 게이트 미적용 | 실패 코드 배포 가능 | resolved | A-011-7 | CI `test` 선행 및 build/deploy 의존 게이트 적용 완료 |
| TD-009 | Deployment | dev push 즉시 배포 구조 | 운영 실수 영향 확대 | open | (TBD) | CI/CD 정책 분리 문서화 후 적용 |
| TD-010 | Modeling | 모델 인터페이스 미구현 | 모델 교체 비용 증가 | open | D-001 | BaseModel 추상화 도입 |
| TD-011 | Modeling | shadow 추론/평가 파이프라인 미구현 | 모델 비교 근거 부족 | open | D-003,D-004 | shadow 결과 저장/리포트 구현 |
| TD-012 | Modeling | 자동 재학습/승격 게이트 미구현 | 모델 운영 수작업 부담 | open | D-006,D-007,D-005 | 수동 트리거부터 도입 |
| TD-013 | Reliability | atomic JSON 권한 이슈 (회귀 위험) | nginx 읽기 실패 재발 가능 | mitigated | A-007,A-011-2 | 회귀 테스트 유지 및 CI 연동 |
| TD-014 | Deployment | worker 이미지 ENTRYPOINT 고정으로 monitor 커맨드 충돌 | monitor 오작동/중복 worker 실행 가능 | resolved | A-010-6 | 범용 ENTRYPOINT + worker 기본 CMD로 분리 적용 |
| TD-015 | Data Consistency | Influx-JSON 최신 시각 불일치 자동 검증 미구현 | 운영자가 오래된 JSON을 정상으로 오해할 수 있음 | open | A-014 | Influx 최신 시각 vs static `updated_at` 비교 로직/알림 추가 |
| TD-016 | Alerting | unhealthy 상태 장기 지속 시 재알림 미구현 | 최초 상태전이 알림 유실 시 장애 인지 지연 | open | A-010-7 | 3사이클 이상 지속 시 재알림 + 알림 폭주 억제 테스트 추가 |
| TD-017 | Runtime Guard | Phase B 이전 다중 timeframe 설정 방어 미구현 | `missing` 오탐 증가 및 운영 판단 혼선 | resolved | A-015 | `INGEST_TIMEFRAMES=1h` fail-fast 가드 적용 완료 |
| TD-018 | Serving Policy | API-SSG 경계 및 endpoint sunset 기준 미정의 | 사용자/운영 경로 혼선, 불필요한 유지비 지속 | open | A-016 | 경계 정책/삭제 조건 문서화 후 점진 정리 |
| TD-019 | Worker Architecture | ingest/predict/export 단일 worker 결합 구조 | 특정 단계 지연/장애가 전체 파이프라인 SLA를 악화 | open | C-005 | 단계별 worker 분리 순서/의존성 정의 후 점진 분리 |
| TD-020 | Scheduling | 고정 간격 while-loop 중심 스케줄 | timeframe별 리소스 낭비/경계 불일치 가능 | open | C-006 | Phase A에서는 단기 패치 없이 defer, C-006에서 timeframe 경계 기반 트리거로 전환 |
| TD-021 | Failure Signaling | predict 실패 시 degraded 상태/알림 표준 미구현 | 마지막 정상값 제공 중 실패 사실이 숨겨질 수 있음 | open | A-017 | soft stale 경고 정책과 분리된 degraded 신호(`degraded`,`last_success_at`)를 노출 |
| TD-022 | Freshness Semantics | prediction 파일 `updated_at` 기반 fresh 판정이 입력 데이터 stale을 가릴 수 있음 | freshness honesty 훼손 및 운영 오판 가능 | open | A-014,A-017 | 입력 데이터 최신 시각과 prediction 생성 시각을 분리 노출하고 정합성 체크 연동 |
| TD-023 | Status Consistency | API와 monitor의 prediction 파일 선택/판정 경로가 분리됨 | 동일 시점 상태 불일치 및 경보 혼선 가능 | resolved | A-018 | `utils/prediction_status.py` 공통 evaluator 도입 및 API/monitor 공용 경로 통합 완료 |
| TD-024 | Alerting | worker 단계별 부분 실패가 운영 알림으로 충분히 승격되지 않음 | 프로세스 생존 상태에서 기능 실패 장기 미탐지 가능 | open | A-017,A-010-7 | 단계 실패를 degraded/alert 이벤트로 승격하고 지속 실패 재알림과 연동 |
| TD-025 | Ingest Recovery | DB last + 30일 룩백 기반 since 결정 | 장기 중단 후 복구 지점 부정확/과다 백필 가능 | resolved | A-002 | `utils/ingest_state.py` 도입으로 `symbol+timeframe` 커서 저장/재시작 복구 기준 고정 완료 |

## 3. 상태 정의
1. `open`: 미해결
2. `in_progress`: 진행 중
3. `mitigated`: 완전 해소 전, 완화 조치 적용
4. `resolved`: 해소 완료
