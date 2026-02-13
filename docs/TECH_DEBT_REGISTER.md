# Coin Predict Technical Debt Register

- Last Updated: 2026-02-13
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
| TD-005 | API | timeframe-aware 파일 네이밍 미완성 | 확장 시 라우팅 혼선 | resolved | B-002 | canonical `{symbol}_{timeframe}` 적용 + legacy 호환(dual-write/dual-read) 유지, 회귀 테스트 통과 |
| TD-006 | API | manifest 미구현 | 상태 가시성 부족 | open | B-004 | manifest 생성 경로 추가 |
| TD-007 | Worker | 워커 경계 조건 테스트 부족 | 회귀 리스크 증가 | resolved | A-011-6 | pagination 종료 경계/리필 병합 경계 테스트 추가 완료 |
| TD-008 | CI/CD | 테스트 게이트 미적용 | 실패 코드 배포 가능 | resolved | A-011-7 | CI `test` 선행 및 build/deploy 의존 게이트 적용 완료 |
| TD-009 | Deployment | dev push 즉시 배포 구조 | 운영 실수 영향 확대 | open | (TBD) | CI/CD 정책 분리 문서화 후 적용 |
| TD-010 | Modeling | 모델 인터페이스 미구현 | 모델 교체 비용 증가 | open | D-001 | BaseModel 추상화 도입 |
| TD-011 | Modeling | shadow 추론/평가 파이프라인 미구현 | 모델 비교 근거 부족 | open | D-003,D-004 | shadow 결과 저장/리포트 구현 |
| TD-012 | Modeling | 자동 재학습/승격 게이트 미구현 | 모델 운영 수작업 부담 | open | D-006,D-007,D-005 | 수동 트리거부터 도입 |
| TD-013 | Reliability | atomic JSON 권한 이슈 (회귀 위험) | nginx 읽기 실패 재발 가능 | mitigated | A-007,A-011-2 | 회귀 테스트 유지 및 CI 연동 |
| TD-014 | Deployment | worker 이미지 ENTRYPOINT 고정으로 monitor 커맨드 충돌 | monitor 오작동/중복 worker 실행 가능 | resolved | A-010-6 | 범용 ENTRYPOINT + worker 기본 CMD로 분리 적용 |
| TD-015 | Data Consistency | Influx-JSON 최신 시각 불일치 검증 미구현 | 운영자가 오래된 JSON을 정상으로 오해할 수 있음 | resolved | A-014 | Influx 최신 시각 vs static `updated_at` 비교/승격 로직 구현 + `/predict` 미래값 운영 스모크체크(전체 심볼) 확인 완료 |
| TD-016 | Alerting | unhealthy 상태 장기 지속 시 재알림 미구현 | 최초 상태전이 알림 유실 시 장애 인지 지연 | resolved | A-010-7 | hard_stale/corrupt/missing 3사이클 재알림 + soft_stale 연속 3사이클 재알림 구현/테스트 완료 |
| TD-017 | Runtime Guard | Phase B 이전 다중 timeframe 설정 방어 미구현 | `missing` 오탐 증가 및 운영 판단 혼선 | resolved | A-015 | `INGEST_TIMEFRAMES=1h` fail-fast 가드 적용 완료 |
| TD-018 | Serving Policy | API-SSG 경계 및 endpoint sunset 기준의 운영 계약(필드/경로) 미확정 | 사용자/운영 경로 혼선, 불필요한 유지비 지속 | mitigated | A-016,B-005 | 1차 경계/체크리스트 문서화는 완료. 프론트 요구 필드 계약과 운영 API(`/status`, 필요 시 `/ops/*`) 범위를 확정한 뒤 `B-005`에서 endpoint 삭제 실행 |
| TD-019 | Worker Architecture | ingest/predict/export 단일 worker 결합 구조 | 특정 단계 지연/장애가 전체 파이프라인 SLA를 악화 | open | C-005 | 단계별 worker 분리 순서/의존성 정의 후 점진 분리 |
| TD-020 | Scheduling | 고정 간격 while-loop 중심 스케줄 | timeframe별 리소스 낭비/경계 불일치 가능 | open | C-006,C-007 | `D-2026-02-13-33` 기준으로 `C-006(UTC boundary scheduler) -> C-007(new closed candle detection gate)` 순서로 전환 |
| TD-021 | Failure Signaling | predict 실패 시 degraded 상태/알림 표준 미구현 | 마지막 정상값 제공 중 실패 사실이 숨겨질 수 있음 | resolved | A-017 | worker predict 실패/복구 상태전이 알림 + `/status` degraded/last success/failure 노출 적용 완료 |
| TD-022 | Freshness Semantics | prediction 파일 `updated_at` 기반 fresh 판정이 입력 데이터 stale을 가릴 수 있음 | freshness honesty 훼손 및 운영 오판 가능 | open | A-014,A-017 | A-014 정합성 체크 운영 검증은 완료, 입력 데이터 최신 시각(`ohlcv_last`)의 사용자 노출 경로 추가 검토 필요 |
| TD-023 | Status Consistency | API와 monitor의 prediction 파일 선택/판정 경로가 분리됨 | 동일 시점 상태 불일치 및 경보 혼선 가능 | resolved | A-018 | `utils/prediction_status.py` 공통 evaluator 도입 및 API/monitor 공용 경로 통합 완료 |
| TD-024 | Alerting | worker 단계별 부분 실패가 운영 알림으로 충분히 승격되지 않음 | 프로세스 생존 상태에서 기능 실패 장기 미탐지 가능 | mitigated | A-017,A-010-7 | predict 상태전이/지속재알림은 반영됨. ingest/export 단계 세분화 알림은 C-005 분리 이후 재평가 |
| TD-025 | Ingest Recovery | DB last + 30일 룩백 기반 since 결정 | 장기 중단 후 복구 지점 부정확/과다 백필 가능 | resolved | A-002 | `utils/ingest_state.py` 도입으로 `symbol+timeframe` 커서 저장/재시작 복구 기준 고정 완료 |
| TD-026 | Maintainability | 주석/로그 밀도가 경로별로 불균등함 | 신규 세션/회귀 분석 시 의도 파악 지연 | mitigated | A-019,C-005 | 핵심 경로 1차 보강은 완료. 신규 복잡 분기 추가 시 동일 기준(의도 주석 + 상태전이 로그) 즉시 적용 |
| TD-027 | Serving Policy | `1m` 예측/서빙 경계가 불명확함(예측 비서빙 vs 제공 경로) | candle 경계 내 오버런, 의미 낮은 예측 노출, FE 계약 혼선 | open | B-001,B-003 | `1m`은 prediction 비서빙 + hybrid API(`latest closed 180`) 경계를 정책/테스트로 고정 |
| TD-028 | Storage Budget | 다중 심볼 `1m` 원본 장기 보관 전략 부재 | Free Tier 50GB 초과로 쓰기 실패/운영 중단 가능 | open | B-006 | rolling retention(`14d default / 30d cap`) + disk watermark 경보/차단 + 용량 추세 검증 |
| TD-029 | Data Lineage | `1h->1d/1w/1M` downsample 경로/검증 기준 미정 | timeframe 간 정합성 불일치, 재현성 저하 | open | B-001,B-006 | downsample 소스/주기/검증식을 명시하고 회귀 테스트 추가 |
| TD-030 | Modeling Guard | 장기 timeframe 최소 샘플 부족 시 예측 차단/품질표시 정책 미구현 | 통계적 신뢰도 부족한 예측이 정상처럼 노출될 수 있음 | open | D-010 | Hard Gate(`insufficient_data`) + Accuracy Signal(`mae/smape/directional/sample_count`) 표준화 |

## 3. 상태 정의
1. `open`: 미해결
2. `in_progress`: 진행 중
3. `mitigated`: 완전 해소 전, 완화 조치 적용
4. `resolved`: 해소 완료
