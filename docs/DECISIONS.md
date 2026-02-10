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
