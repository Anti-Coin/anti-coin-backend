# Coin Predict 테스트 전략 (Living)

- Last Updated: 2026-02-10
- Scope: 백엔드 안정성/에러처리 중심
- Mode: Incremental TDD

## 1. 목적
1. 배포 후에만 발견되는 장애를 사전에 차단한다.
2. 최근 이슈(권한/정적 파일 접근 실패)를 회귀 테스트로 고정한다.
3. 코드 추가 시 테스트가 동반되는 습관을 팀 기본값으로 만든다.

## 2. 원칙
1. 작은 기능 단위로 테스트를 붙인다.
2. 정상 경로와 실패 경로를 동일 비중으로 다룬다.
3. 불안정한 외부 의존(거래소/DB)은 mock/stub 우선으로 검증한다.
4. 테스트 실패 원인이 모호하면 테스트 자체를 먼저 단순화한다.

## 3. 우선 테스트 매트릭스
| 영역 | 시나리오 | 유형 | 우선순위 |
|---|---|---|---|
| File IO | JSON 쓰기 성공/교체/권한 | unit | P1 |
| File IO | dump 실패 시 temp 파일 정리 | unit | P1 |
| Freshness | fresh/stale/hard_stale/corrupt 분류 | unit | P1 |
| API Status | 파일 없음/파손/포맷오류 처리 | unit | P1 |
| API Status | soft stale 경고 응답/hard stale 차단 | unit | P1 |
| Config | env 파싱 경계조건 | unit | P2 |
| Worker | fetch pagination 경계조건 | unit | P2 |

## 4. TDD 루프 (실무형)
1. 실패 재현 테스트 작성 (Red)
2. 최소 코드 수정으로 통과 (Green)
3. 중복/가독성 정리 (Refactor)
4. 회귀 테스트로 문서/태스크 업데이트

## 5. 완료 기준
1. 테스트 명령 1개로 실행 가능 (`pytest`)
2. P1 매트릭스 시나리오는 모두 자동화
3. 신규 버그 수정은 최소 1개 회귀 테스트 포함

## 6. 보류 기준
아래 조건이면 즉시 확장 중단하고 범위를 줄인다.
1. 테스트 코드가 실제 코드보다 복잡해짐
2. 외부 의존 모킹이 과도해져 유지보수 비용 급증
3. 테스트 불안정(flaky)으로 신뢰도 저하
