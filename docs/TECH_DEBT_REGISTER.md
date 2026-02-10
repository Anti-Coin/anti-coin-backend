# Coin Predict Technical Debt Register

- Last Updated: 2026-02-10
- Purpose: 기술 부채를 세션 간 누락 없이 추적

## 1. 운용 규칙
1. 코드 변경 후 새 부채가 생기면 즉시 항목을 추가한다.
2. 부채 해소 시 `status`를 `resolved`로 바꾸고 근거를 남긴다.
3. 정책/우선순위 변경은 `DECISIONS`와 함께 기록한다.

## 2. Debt List
| ID | Category | Debt | Risk | Status | Linked Task | Next Action |
|---|---|---|---|---|---|---|
| TD-001 | Ingest | closed candle 경계 미구현 | 미완료 캔들 저장 가능성 | open | A-004 | 경계 계산 유틸 추가 후 fetch 경로 적용 |
| TD-002 | Ingest | gap detector 미구현 | 데이터 누락 장기화 가능 | open | A-005 | 누락 구간 계산 로직 추가 |
| TD-003 | Ingest | gap refill 잡 미구현 | 누락 자동 복구 불가 | open | A-006 | gap 기반 재수집 루틴 구현 |
| TD-004 | Alerting | hard_stale/corrupt/missing/recovery 알림 미연동 | 운영자 탐지 지연 | mitigated | A-010 | 배포 환경에서 monitor 서비스 기동/알림 확인 후 `resolved` 전환 |
| TD-005 | API | timeframe-aware 파일 네이밍 미완성 | 확장 시 라우팅 혼선 | open | B-002 | 파일명 규칙 통일 |
| TD-006 | API | manifest 미구현 | 상태 가시성 부족 | open | B-004 | manifest 생성 경로 추가 |
| TD-007 | Worker | 워커 경계 조건 테스트 부족 | 회귀 리스크 증가 | open | A-011-6 | fetch pagination 테스트 추가 |
| TD-008 | CI/CD | 테스트 게이트 미적용 | 실패 코드 배포 가능 | open | A-011-7 | 배포 전 테스트 단계 강제 |
| TD-009 | Deployment | dev push 즉시 배포 구조 | 운영 실수 영향 확대 | open | (TBD) | CI/CD 정책 분리 문서화 후 적용 |
| TD-010 | Modeling | 모델 인터페이스 미구현 | 모델 교체 비용 증가 | open | D-001 | BaseModel 추상화 도입 |
| TD-011 | Modeling | shadow 추론/평가 파이프라인 미구현 | 모델 비교 근거 부족 | open | D-003,D-004 | shadow 결과 저장/리포트 구현 |
| TD-012 | Modeling | 자동 재학습/승격 게이트 미구현 | 모델 운영 수작업 부담 | open | D-006,D-007,D-005 | 수동 트리거부터 도입 |
| TD-013 | Reliability | atomic JSON 권한 이슈 (회귀 위험) | nginx 읽기 실패 재발 가능 | mitigated | A-007,A-011-2 | 회귀 테스트 유지 및 CI 연동 |
| TD-014 | Deployment | worker 이미지 ENTRYPOINT 고정으로 monitor 커맨드 충돌 | monitor 오작동/중복 worker 실행 가능 | resolved | A-010-6 | 범용 ENTRYPOINT + worker 기본 CMD로 분리 적용 |

## 3. 상태 정의
1. `open`: 미해결
2. `in_progress`: 진행 중
3. `mitigated`: 완전 해소 전, 완화 조치 적용
4. `resolved`: 해소 완료
