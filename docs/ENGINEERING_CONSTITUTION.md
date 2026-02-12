# Coin Predict Engineering Constitution

- Last Updated: 2026-02-12
- Purpose: 구현/검증/변경 시 공통 기준

## 1. 판단 우선순위
1. Stability
2. Cost/Operability
3. Performance

## 2. 구현 원칙
1. One task, one purpose
2. Small patch default
3. No silent failure
4. Idempotency first
5. UTC internally

## 3. 오류 처리 원칙
1. 정상 경로와 실패 경로를 같은 비중으로 설계한다.
2. 예외를 잡을 때는 의도한 예외를 먼저 분리 처리한다.
3. 도메인 정책에 맞춰 degrade/차단 기준을 명시한다.
4. 운영자가 원인 파악 가능한 로그/메시지를 남긴다.

## 4. 테스트 원칙
1. 버그 수정은 회귀 테스트를 기본값으로 한다.
2. 신규 동작은 성공/실패 케이스를 최소 1개씩 포함한다.
3. 테스트 미작성은 예외가 아니라 부채이며 후속 ID를 남긴다.

## 5. 완료 정의 (Definition of Done)
1. 코드 변경
2. 검증 증거(자동/수동/런타임) 확보
3. 관련 문서(`PLAN`, `TASKS`, `DECISIONS`, `TECH_DEBT`) 갱신

## 6. 변경 관리
1. 정책 변경은 `DECISIONS`에 먼저 기록한다.
2. 계획 변경은 `PLAN`과 `TASKS`에 반영한다.
3. 부채 생성/해소는 `TECH_DEBT_REGISTER`에 기록한다.

## 7. 가독성/관측성 기준
1. 복잡한 분기/조기 반환(early return)에는 "왜 이 분기가 필요한지"를 짧은 주석으로 남긴다.
2. 주석은 구현을 그대로 번역하지 말고, 의도/운영 리스크/실패 방지 이유를 설명한다.
3. 로그는 운영자가 장애 원인을 추적할 수 있도록 상태전이(실패 시작/복구/지속)를 우선 기록한다.
4. 정상 반복 경로의 과도한 로그 스팸은 피하고, 필요 시 요약 로그 또는 상태전이 로그를 사용한다.
