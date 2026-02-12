# Coin Predict 결정 로그 (ADR-lite)

이 문서는 프로젝트의 핵심 선택과 변경 이력을 짧게 기록한다.

## D-2026-02-10-01
- Date: 2026-02-10
- Status: Accepted
- Context:
  - Timeframe 확장(1d, 1M 포함)과 운영 안정성을 동시에 고려해야 함
  - Free Tier 환경에서 비용/복잡도 균형 필요
- Decision:
  - Ingest는 Hybrid 전략 채택
  - 1m은 rolling window 수집, 1d/1w/1M은 직접 수집
- Consequence:
  - 전구간 1m 수집 대비 초기 비용 감소
  - 타임프레임별 정책 관리 필요

## D-2026-02-10-02
- Date: 2026-02-10
- Status: Accepted
- Context:
  - stale 데이터 처리 정책 필요
- Decision:
  - Soft stale 노출 허용, 단 경고를 반드시 표기
  - hard_stale/corrupt는 차단
- Consequence:
  - 서비스 연속성 확보
  - 상태 분류 로직 및 경고 표준 필요

## D-2026-02-10-03
- Date: 2026-02-10
- Status: Accepted
- Context:
  - `admin/app.py` 성격 혼선
- Decision:
  - `admin/app.py`는 백엔드 개발자 점검용 도구로 정의
  - 운영 데이터 플레인의 정책 판단 기준에서 분리
- Consequence:
  - 운영 정책 논의 시 사용자 경로와 점검 도구를 분리해서 평가

## D-2026-02-10-04
- Date: 2026-02-10
- Status: Accepted
- Context:
  - 초기 계획에 매몰되지 않기 위한 운영 원칙 필요
  - 모델 자동화(인터페이스/Shadow/재학습)는 우선순위 재조정 가능성이 큼
- Decision:
  - 계획은 Living Plan으로 운용한다.
  - 모델 자동화 트랙은 문서에 명시하되, 순서/타이밍은 상황에 따라 조정한다.
- Consequence:
  - 기능 누락 없이 로드맵 가시성 확보
  - 일정 지연 시 문서 갱신을 통해 합의 상태를 유지

## D-2026-02-10-05
- Date: 2026-02-10
- Status: Accepted
- Context:
  - 로컬 전체 실행 없이 원격 배포 환경에서 버그 발견 지연
  - 최근 파일 권한 이슈가 배포 후 발견됨
- Decision:
  - 테스트 확장은 Incremental TDD 방식으로 진행한다.
  - 우선순위는 파일 I/O, freshness, status 에러처리, config 파서 순으로 둔다.
- Consequence:
  - 회귀 장애를 테스트로 고정 가능
  - 대규모 일괄 도입 대신 작은 단위로 품질을 축적

## D-2026-02-10-06
- Date: 2026-02-10
- Status: Accepted
- Context:
  - 세션이 길어질수록 맥락 오염 리스크가 커짐
  - 세션 전환 시 철학/목표/제약 재정렬 비용이 큼
- Decision:
  - 문서 운영체계를 도입한다.
  - `PROJECT_IDENTITY`와 `도메인 정책`을 분리해서 관리한다.
  - 기술 부채는 별도 레지스터로 누적 관리한다.
- Consequence:
  - 새 세션 시작 시 정렬 속도 향상
  - 논의 누락/중복 가능성 감소

## D-2026-02-10-07
- Date: 2026-02-10
- Status: Accepted
- Context:
  - `/status`는 프론트엔드 경고 판단을 위한 경로이며 호출 의존성이 있음
  - 운영 알림은 호출 유무와 무관하게 백엔드에서 지속 감시 필요
- Decision:
  - A-010은 별도 모니터 스크립트로 구현한다.
  - 알림 이벤트는 `hard_stale`, `corrupt`, `missing`, `recovery` 상태전이에 제한한다.
  - `stale(soft)`는 알림 대상이 아니라 경고 노출 대상이다.
- Consequence:
  - Worker 다운/호출 부재 상황에서도 상태 감시 가능
  - 알림 노이즈 감소 (상태전이 기반)

## D-2026-02-10-08
- Date: 2026-02-10
- Status: Accepted
- Context:
  - worker 이미지가 고정 ENTRYPOINT로 `pipeline_worker`를 강제해 monitor 실행과 충돌
  - monitor 서비스에서 command override가 의도대로 적용되지 않는 위험 확인
- Decision:
  - worker 이미지는 범용 ENTRYPOINT(umask 설정 + exec) + 기본 CMD(`pipeline_worker`) 구조로 전환
  - monitor는 compose `command`로 `scripts.status_monitor`를 실행한다.
- Consequence:
  - worker/monitor 공용 이미지 재사용 가능
  - monitor가 별도 Dockerfile 없이 독립 프로세스로 실행 가능

## D-2026-02-10-09
- Date: 2026-02-10
- Status: Accepted
- Context:
  - InfluxDB와 정적 JSON을 동시에 운용하면서 데이터 권위(Source of Truth) 경계가 문서상 명시되지 않음
  - 장애 대응 시 "무엇을 기준으로 복구/검증할지" 판단 기준이 필요
- Decision:
  - 데이터 권위는 InfluxDB로 고정한다.
  - 정적 JSON은 사용자 제공을 위한 파생 산출물(derived artifact)로 정의한다.
- Consequence:
  - 복구/검증은 InfluxDB 기준으로 수행한다.
  - 정적 JSON은 재생성 가능한 산출물로 취급한다.

## D-2026-02-10-10
- Date: 2026-02-10
- Status: Accepted
- Context:
  - 예측 시작 시점을 `now` 기준 rolling으로 두면 실행 시각마다 타임스탬프가 흔들려 비교/회귀 평가가 어려움
  - 시계열 정합성과 운영 일관성을 위해 경계 정렬 필요
- Decision:
  - 예측 시작 시점은 각 timeframe의 "다음 closed candle 경계(UTC)"로 고정한다.
  - `now` rolling 시작 방식은 사용자 제공 경로에서 사용하지 않는다.
- Consequence:
  - 예측 결과의 시간축 정렬이 고정되어 비교/모니터링/회귀 분석이 쉬워진다.
  - 캔들 경계 유틸의 정확성이 중요해진다.

## D-2026-02-10-11
- Date: 2026-02-10
- Status: Accepted
- Context:
  - 모든 변경마다 전 문서를 갱신하면 토큰/운영 비용이 과도해짐
  - 반대로 문서를 너무 줄이면 세션 전환 시 맥락 손실이 커짐
- Decision:
  - 문서 갱신은 "코드-only 생략 가능 + 조건부 필수 갱신" 정책을 채택한다.
  - 새 기술 부채가 생기면 `TECH_DEBT_REGISTER` 갱신은 필수다.
  - 기존 계획 수행 불가 상태가 되면 `PLAN`과 `TASKS`를 즉시 갱신한다.
- Consequence:
  - 문서 비용을 통제하면서도 중요한 결정/리스크는 추적 가능하다.
  - 문서 누락으로 인한 재논의 비용을 줄일 수 있다.

## D-2026-02-12-12
- Date: 2026-02-12
- Status: Accepted
- Context:
  - `admin/app.py`가 Streamlit 기반이라 제품 프론트엔드 경로와 혼동될 수 있음
  - 실제 사용자 프론트엔드는 Vue/React 계열로 별도 구축할 계획임
- Decision:
  - 제품 사용자 경로의 프론트엔드는 Vue/React(또는 동급 SPA) 계열로 별도 운용한다.
  - `admin/app.py`는 개발자 점검/테스트용 대시보드로 한정한다.
- Consequence:
  - 제품 프론트엔드 성능/캐시/인증 설계와 Streamlit 운영을 분리해서 의사결정한다.
  - Streamlit 변경이 사용자 경로 SLA의 직접 기준이 되지 않는다.

## D-2026-02-12-13
- Date: 2026-02-12
- Status: Accepted
- Context:
  - 현재 worker/export/API/monitor는 다중 timeframe 정합성이 완성되지 않았음
  - `INGEST_TIMEFRAMES`를 성급히 확장하면 `missing` 노이즈와 파일 규칙 불일치 위험이 있음
- Decision:
  - Phase B(Timeframe Expansion) 완료 전까지 운영 설정은 `INGEST_TIMEFRAMES=1h`로 고정한다.
  - 다중 timeframe 전환은 worker/API/monitor/export를 한 번에 확장하는 배치 변경으로만 수행한다.
- Consequence:
  - 운영 중 잘못된 알림 노이즈를 줄이고 장애 판단 기준을 단순화한다.
  - 확장 시점에는 경계 조건 테스트와 파일 네이밍 정책을 함께 검증해야 한다.

## D-2026-02-12-14
- Date: 2026-02-12
- Status: Accepted
- Context:
  - `/history`, `/predict` 엔드포인트는 초기 구조의 잔재지만 즉시 삭제는 아님
  - Free Tier 제약에서 SSG 중심 전략이 비용 효율적이나, 운영/디버그 경로는 필요함
- Decision:
  - 사용자 제공의 기본 데이터 플레인은 SSG(static JSON)로 유지한다.
  - `/history`, `/predict`는 당분간 운영/디버그 fallback 경로로 유지하고, sunset 조건이 확정되면 제거를 검토한다.
- Consequence:
  - 비용 효율성을 유지하면서도 운영 관측/디버깅 유연성을 확보한다.
  - 사용자 경로와 운영 경로의 책임 경계를 문서/태스크로 지속 관리해야 한다.

## D-2026-02-12-15
- Date: 2026-02-12
- Status: Accepted
- Context:
  - 현재 알림은 상태전이 기반이라, 최초 이벤트 알림을 놓치면 장기 장애 인지가 지연될 수 있음
- Decision:
  - unhealthy 상태(`hard_stale/corrupt/missing`)가 3사이클 이상 지속되면 재알림을 보낸다.
  - 구현은 즉시 적용하지 않고 `A-011-7`(CI 테스트 게이트) 이후 작은 후속 태스크로 처리한다.
- Consequence:
  - 장기 장애의 탐지 안정성이 향상된다.
  - 재알림 도입 시 알림 폭주를 막기 위한 간격/중복 억제 기준이 필요하다.

## D-2026-02-12-16
- Date: 2026-02-12
- Status: Accepted
- Context:
  - ingest pagination 수집 시점에는 아직 닫히지 않은(candle close 미완료) 봉이 포함될 수 있음
  - 미완료 봉 저장은 다음 사이클에서 값 변경/덮어쓰기를 유발해 데이터 일관성 판단을 어렵게 만듦
- Decision:
  - ingest 저장 경로는 timeframe별 latest closed candle 경계(UTC)까지만 저장한다.
  - latest closed candle 이후(진행 중) 봉은 해당 사이클에서 저장하지 않는다.
- Consequence:
  - 저장 데이터의 시간 정합성과 재현성이 개선된다.
  - 실시간성은 최대 1캔들 구간 지연될 수 있으나, 안정성/무결성을 우선한다.

## D-2026-02-12-17
- Date: 2026-02-12
- Status: Accepted
- Context:
  - 현재 `pipeline_worker`는 ingest/predict/export를 단일 루프에서 모두 수행하고 있음
  - 특정 단계 지연/장애가 전체 파이프라인 오버런과 제공 지연으로 전파될 위험이 있음
- Decision:
  - worker 역할 분리(ingest/predict/export)를 Phase C의 공식 트랙(`C-005`)으로 채택한다.
  - 분리는 일괄 재작성 대신 단계적 전환(엔트리포인트 분리 -> compose 배치 분리 -> 관측 기반 튜닝)으로 진행한다.
- Consequence:
  - 장애 격리와 운영 탄력성이 개선된다.
  - 서비스 수/배포 복잡도 증가를 감수해야 하며, 메트릭/알림 기준 동반 정리가 필요하다.
