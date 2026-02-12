# Coin Predict Living Plan (Hybrid + Soft Stale)

- Last Updated: 2026-02-12
- Owner: Backend/Platform
- Status: Active

## 1. 문서 목적
이 문서는 현재 합의된 전략을 기준으로, 실제 운영 결과에 따라 변경 가능한 실행 계획을 관리한다.

## 1.1 문서 운영체계
1. 문서 진입점은 `docs/README.md`를 사용한다.
2. 철학/정체성은 `docs/PROJECT_IDENTITY.md`를 기준으로 한다.
3. 기술 부채 상태는 `docs/TECH_DEBT_REGISTER.md`를 기준으로 한다.
4. 세션 인수인계는 `docs/SESSION_HANDOFF.md`를 기준으로 한다.

## 1.2 계획 운용 원칙 (Living Plan)
1. 이 문서는 고정 사양서가 아니라 변경 가능한 운영 계획이다.
2. 우선순위와 순서는 운영 리스크, 리소스, 실험 결과에 따라 바뀔 수 있다.
3. 특정 기능(예: 자동 재학습)이 늦어져도 문서를 갱신하고 다음 최적 순서로 재배치한다.
4. 계획 변경은 실패가 아니라 리스크 제어 활동으로 취급한다.

## 2. 확정된 결정 (Fixed)
1. Ingest 전략은 Hybrid를 사용한다.
2. Stale 정책은 Soft Stale 노출 허용(경고 표시)으로 간다.
3. Corrupt 데이터와 Hard Stale 데이터는 차단한다.
4. `admin/app.py`는 운영 데이터 플레인이 아닌 개발자 점검 도구로 취급한다.
5. 1분봉은 초기 단계에서 예측 제공 대상이 아니다.
6. 데이터 권위(Source of Truth)는 InfluxDB로 고정한다.
7. 예측 시작 시점은 timeframe별 다음 closed candle 경계(UTC)로 고정한다.
8. Phase B 전까지 운영 타임프레임 설정은 `1h` 단일값으로 고정한다.
9. `soft stale`(경고 노출)와 `degraded`(운영 실패 신호)는 분리해서 운용한다.

## 3. 목표와 비목표
### 목표
1. 데이터 수집/복구 신뢰성 확보
2. Timeframe 확장 가능한 구조 확보
3. 운영 리소스(Oracle Free Tier) 내에서 안정 운용

### 비목표
1. 초기 단계에서 대규모 MLOps 플랫폼 도입(MLflow/Airflow)
2. 1분봉 예측 API 제공
3. 단일 스프린트 내 전 기능 동시 최적화

## 4. 전략 개요
1. 1m: Rolling Window 수집/보관 (예: 최근 90~180일)
2. 1d/1w/1M: 장기 이력 직접 수집
3. 모델 입력 전처리에서만 Forward Fill 허용 (원천 시계열 오염 방지)
4. 신선도 상태를 `fresh/stale/hard_stale/corrupt`로 분리
5. 사용자 제공용 예측 타임스탬프는 rolling now가 아닌 candle 경계 기준으로 정렬
6. prediction은 InfluxDB에 보존하고, 실패 시 last-good 제공 + degraded 신호를 분리한다.

## 5. 단계별 로드맵
## Phase A: Reliability Baseline
목표: 수집 누락/중단에 대한 복구 가능성 확보

범위:
1. ingest state 관리 도입(`symbol,timeframe,last_closed_ts,status`)
2. 백필 pagination 루프 구현
3. gap detector + 재수집 잡
4. 원자적 JSON 쓰기(임시 파일 + rename)
5. Freshness 분류 유틸 도입
6. API/monitor 상태 판정 경로 공통화
7. predict 실패/부분 실패 신호를 `degraded`로 분리 노출
8. Influx-JSON 정합성 점검과 `/predict` 미래값 운영 스모크체크를 완료

Exit Criteria:
1. 의도적 워커 중단 시 복구 후 데이터 연속성 보장
2. 데이터 누락 시 자동 또는 수동 트리거로 재수집 가능
3. 파손 파일/부분 파일 노출 없음
4. API와 monitor가 동일 기준으로 상태를 판정
5. `soft stale` 경고와 `degraded` 실패 신호가 혼선 없이 분리 노출
6. Influx-JSON 정합성 점검 및 `/predict` 미래값 스모크체크 결과가 기록됨

## Phase B: Timeframe Expansion
목표: 1h 중심 구조에서 다중 timeframe 구조로 전환

범위:
1. timeframe별 수집 정책 분리
2. 파일 네이밍 표준화 (`prediction_{SYMBOL}_{TF}.json`)
3. status/manifest에 timeframe별 신선도 반영

Exit Criteria:
1. 1h/1d/1w/1M 수집 동시 운용 가능
2. 각 timeframe 신선도 임계값 독립 관리 가능

## Phase C: Scale and Ops
목표: 심볼 확장과 운영 관측성 강화

진입 조건:
1. `A-002`, `A-018`, `A-014`, `A-017`, `A-010-7` 완료
2. 위 조건 충족 전에는 C 태스크를 설계/문서 작업으로만 진행

범위:
1. Top N 심볼 확장
2. 작업 시간/오버런/실패율 메트릭 수집
3. 단계적 부하 테스트와 튜닝
4. pipeline worker 역할 분리(ingest/predict/export)로 장애 전파 범위 축소
5. timeframe 경계/새 closed candle 감지 기반 트리거 전환

Exit Criteria:
1. 목표 심볼 수에서 주기적 작업 안정 수행
2. 오버런/실패율 추세 관측 가능
3. ingest 지연/장애가 예측 산출물 갱신 경로를 즉시 중단시키지 않음
4. 고정 간격 루프 대비 불필요 cycle 감소 및 캔들 경계 정합성 개선

## Phase D: Model Evolution (변경 가능 트랙)
목표: 모델 실험/교체/자동화가 가능한 구조를 서비스 안정성 훼손 없이 도입

범위:
1. 모델 인터페이스(`fit/predict/save/load`) 추상화
2. Shadow 모델 추론 경로 구축(서빙 영향 없음)
3. 자동 재학습 잡(수동 트리거 우선, 이후 스케줄)
4. 품질 게이트 기반 승격/롤백 규칙 도입

Exit Criteria:
1. Champion(현재 서빙 모델)과 Shadow(후보 모델) 비교 리포트 생성 가능
2. 재학습 실행과 서빙 경로가 분리되어 장애 전파 없음
3. 품질 게이트 미달 시 자동 승격 금지

## 6. 정책: Soft Stale
1. `fresh`: 정상
2. `stale`: 데이터 제공 + 경고 표시
3. `hard_stale`: 제공 차단
4. `corrupt`: 제공 차단

기본 원칙:
1. 히스토리 데이터는 `stale` 상태에서 경고와 함께 제공 가능
2. 예측 데이터는 `hard_stale` 기준을 더 엄격하게 설정

## 7. 변경 관리 규칙
1. Fixed 항목을 바꾸려면 `docs/DECISIONS.md`에 결정 로그를 남긴다.
2. Phase 범위 변경 시 이 문서의 Last Updated를 갱신한다.
3. Task 추가/삭제는 `docs/TASKS_MINIMUM_UNITS.md`에서 먼저 반영한다.
4. 모델 자동화 관련 순서 변경 시, 변경 이유(성능/안정성/리소스)를 한 줄 이상 기록한다.
5. 작업으로 발생한 기술 부채는 `docs/TECH_DEBT_REGISTER.md`에 반영한다.
6. 코드-only 변경(외부 동작 불변)은 문서 갱신을 생략할 수 있다.
7. 계획 수행 불가 상태가 발생하면 `PLAN`과 `TASKS`를 같은 세션에서 함께 갱신한다.

## 8. 리스크와 대응
1. Exchange API rate limit: pagination 속도 제한/재시도 백오프
2. 대량 백필 시간 증가: 단계별 백필 우선순위
3. 데이터 품질 이슈: 원천 데이터와 보간 데이터 분리
4. 단일 worker 결합 구조: ingest/predict/export 동시 실행으로 오버런/장애 전파 위험
5. artifact freshness와 입력 데이터 freshness가 분리되지 않으면 상태 오판 가능

## 9. 테스트/에러처리 전략 (Incremental)
원칙:
1. 테스트는 "많이"보다 "지속적으로 실패를 조기에 잡는 구조"를 우선한다.
2. 로컬 전체 실행이 어려운 환경을 고려해 단위 테스트 중심으로 시작한다.
3. 에러처리 로직은 정상 경로와 같은 비중으로 테스트한다.
4. 대규모 일괄 테스트 도입 대신, 기능 단위로 테스트를 함께 확장한다.

우선순위:
1. 파일 I/O 안정성 (`atomic_write_json` 권한/교체/실패 복구)
2. Freshness 분류 로직 (`fresh/stale/hard_stale/corrupt`)
3. Status API 에러 처리(HTTPException passthrough, 포맷 오류 처리)
4. 설정 파서(환경변수 파싱 안전성)

완료 정의:
1. 장애 재현 이슈(권한/파손/stale)가 테스트로 고정된다.
2. 신규 기능 PR은 최소 1개 이상의 자동 테스트를 포함한다.
3. 테스트 실패 시 배포 전 단계에서 중단 가능해야 한다.

## 10. 진행 현황
1. 2026-02-10: A-001(설정 중앙화) 완료
2. 2026-02-10: A-003(ccxt 백필 pagination 루프) 완료
3. 2026-02-10: A-007(원자적 JSON 쓰기) 완료
4. 2026-02-10: A-008(freshness 분류 유틸) 완료
5. 2026-02-10: A-009(status soft stale/hard stale 정책 반영) 완료
6. 2026-02-10: A-011(테스트 체계) 진행 중 - 세부 A-011-1~5 완료
7. 2026-02-10: A-012(세션 정렬 문서 체계) 완료
8. 2026-02-10: 문서 운영체계(정체성/제약/부채/핸드오프) 추가
9. 2026-02-10: A-010(상태전이 알림 모니터) 완료
10. 2026-02-10: A-010 후속 패치(ENTRYPOINT/CMD 충돌 해결) 완료
11. 2026-02-10: 이번 작업에서 Phase/우선순위 변경 없음
12. 2026-02-10: 데이터 권위(Source of Truth)를 InfluxDB로 명시
13. 2026-02-10: 예측 시작 시점을 candle 경계 기준으로 정렬
14. 2026-02-12: A-004 완료 (closed candle 경계 기반 미완료 캔들 저장 차단)
15. 2026-02-12: A-015 완료 (Phase B 전 `INGEST_TIMEFRAMES=1h` 운영 가드 반영)
16. 2026-02-12: worker 역할 분리 필요성 확인, Phase C 범위에 분리 트랙(C-005) 추가
17. 2026-02-12: A-005 완료 (gap detector 도입, 누락 구간 감지/경고 기반 확보)
18. 2026-02-12: prediction 보존/실패 신호/trigger 전환 정책 결정(D-2026-02-12-18)
19. 2026-02-12: Phase A 우선순위 재정렬 및 `soft stale`/`degraded` 분리 정책 확정(D-2026-02-12-19~22)
20. 2026-02-12: A-018 완료 (API/monitor 상태 판정 경로 공통 evaluator로 통합)
21. 2026-02-12: A-002 완료 (ingest_state 파일 저장소 도입, 커서 기반 재시작 복구 기준 고정)
