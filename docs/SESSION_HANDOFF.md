# Coin Predict Session Handoff

- Last Updated: 2026-02-10
- Branch: `dev`

## 1. 현재 스냅샷
1. Phase A 진행 중
2. 완료: A-001, A-003, A-007, A-008, A-009, A-010
3. 테스트: A-011-1~5 + A-010-4 완료 (`pytest` 26개 통과)
4. monitor 실행 충돌 핫픽스 적용(ENTRYPOINT/CMD 분리)

## 2. 다음 우선 작업
1. A-004: closed candle 경계 유틸
2. A-005: gap detector
3. A-006: gap refill
4. A-011-6: 워커 경계 테스트
5. A-011-7: CI 테스트 게이트 도입

## 3. 현재 리스크
1. CI 테스트 게이트 미적용
2. dev push 즉시 배포 구조 유지
3. 워커 경계조건 테스트 부족

## 4. 빠른 검증 명령
1. `PYENV_VERSION=coin pytest -q`
2. `python -m compileall api utils tests`

## 5. 새 세션 시작 프로토콜
1. `docs/README.md`의 읽기 순서대로 문서를 확인한다.
2. 현재 이해를 5~10줄로 요약한다.
3. 바로 진행할 태스크 1개만 선택해서 시작한다.

## 6. 종료 시 갱신 규칙
1. 완료 태스크와 변경 파일을 추가한다.
2. 새로 생긴 부채를 `TECH_DEBT_REGISTER`에 반영한다.
3. 다음 세션의 첫 작업 후보를 3개 이하로 유지한다.
