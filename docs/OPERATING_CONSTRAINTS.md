# Coin Predict Operating Constraints

- Last Updated: 2026-02-19
- Purpose: 운영 현실/제약을 명시해 과설계를 방지

## 1. 인프라 현실
1. 대상 환경은 Oracle Free Tier ARM이다.
2. 리소스는 제한적이며 장시간 연속 실행 안정성이 중요하다.
3. 운영 복잡도 자체가 비용이다.

## 2. 현재 배포 현실
1. 현재는 `dev/main push` 기반 배포 자동화가 존재한다.
2. 서비스 초기 단계라 운영자 1인 사용 시나리오가 중심이다.
3. 이 구조는 장기적으로 위험하며 추후 분리/승인 게이트가 필요하다.

## 3. 기술/아키텍처 제약
1. 정적 JSON 서빙 구조가 기본 데이터 플레인이다.
2. FastAPI는 상태 확인/운영 제어/호환 종료 신호(tombstone) 중심으로 사용한다.
3. 무거운 오케스트레이션 도구는 조건 충족 전 도입하지 않는다.
4. 데이터 권위(Source of Truth)는 InfluxDB이며, 정적 JSON은 제공용 파생 산출물이다.

## 4. 운영 정책 경계
1. `admin/app.py`는 운영자 점검용 도구다.
2. 사용자 경로 정책과 관리자 점검 경로를 혼동하지 않는다.
3. 도메인 정책(soft stale/hard stale)은 서비스 목적에 따라 조정 가능하다.

## 5. 검증 제약
1. 로컬 전체 스택 실행이 항상 가능하지 않다.
2. 따라서 단위 테스트 + 경량 검증을 우선 채택한다.
3. 배포 이후 검증에만 의존하지 않도록 사전 테스트 게이트를 강화한다.

## 6. 재검토 트리거
아래 조건이 발생하면 이 문서를 갱신한다.
1. 사용자 트래픽 증가
2. 배포 전략 변경
3. 인프라 스펙 변경
4. 주요 장애/근접사고 발생

## 7. 문서 갱신 제약 (Token/운영 비용 기준)
1. 코드-only 변경(외부 동작 불변)은 문서 갱신을 생략할 수 있다.
2. 동작 변경이 있으면 최소 `TASKS`를 갱신하고, 계획 영향이 있으면 `PLAN`을 함께 갱신한다.
3. 정책/아키텍처 판단 변경은 `DECISIONS`를 필수로 기록한다.
4. 새 기술 부채가 생기면 `TECH_DEBT_REGISTER` 갱신은 필수다.
5. 기존 계획대로 수행 불가 상태가 되면 같은 세션에서 `PLAN`과 `TASKS`를 함께 갱신한다.

## 8. API-SSG 경계 정책
1. 사용자 데이터 플레인은 SSG(static JSON)다.
2. 제품 프론트엔드는 `/history`, `/predict`를 호출하지 않는다.
3. FastAPI의 `/status`는 운영 신호 확인 경로로 유지한다.
4. `/history`, `/predict`는 sunset tombstone(`410 Gone`)이며 운영/디버그 정상 경로가 아니다.
5. 추가 점검용 API가 필요하면 사용자 데이터 API와 분리된 운영 경로(`/ops/*`)로 추가한다.
6. `/history`, `/predict`는 호환 종료 신호용 경로로만 남고, 사용자/운영 SLA 경로에 포함하지 않는다.

## 9. Endpoint Sunset 체크리스트
`/history`, `/predict` sunset 완료는 아래 조건을 기준으로 판단한다.
1. 프론트엔드 요구 필드가 SSG + `/status` 조합으로 충족된다.
2. 운영 알림/상태판정(모니터 + `/status`)이 fallback endpoint 없이도 동작한다.
3. 운영 점검(runbook, smoke check)이 fallback endpoint 의존 없이 수행 가능하다.
4. 최소 1회 배포 사이클 fallback 비의존 운영 관측 증거를 확보한다.
5. 필요 시 즉시 복구할 rollback 절차를 문서화한다.

현재 상태(2026-02-19):
1. 1~5 조건을 충족해 `B-005`는 done으로 잠금됐다.
2. rollback runbook은 아래 Section 10을 기준으로 유지한다.

## 10. B-005 Rollback Runbook (FastAPI)
1. `api/main.py`에서 `/history`, `/predict` tombstone 핸들러를 직전 구현으로 복구한다.
2. `PYENV_VERSION=coin pytest -q tests/test_api_status.py`로 API 회귀를 확인한다.
3. fastapi 이미지를 재빌드/재배포한다.
4. 배포 후 `/history/{symbol}`, `/predict/{symbol}`, `/status/{symbol}` 스모크체크를 수행한다.
