# Coin Predict Documentation Index

- Last Updated: 2026-02-12
- Purpose: 새 세션에서 최소 토큰으로 정렬하고, 필요 시에만 깊게 읽기

## 1. Fast Read Order (Default)
1. `docs/CONTEXT_MIN.md`
2. `docs/PROJECT_IDENTITY.md`
3. `docs/OPERATING_CONSTRAINTS.md`
4. `docs/DECISIONS.md`
5. `docs/PLAN_LIVING_HYBRID.md`
6. `docs/TASKS_MINIMUM_UNITS.md`
7. `docs/TECH_DEBT_REGISTER.md`
8. `docs/SESSION_HANDOFF.md`

## 2. Deep Read (When Needed)
1. `docs/ENGINEERING_CONSTITUTION.md`
2. `docs/TEST_STRATEGY.md`
3. `docs/GLOSSARY.md`
4. `docs/archive/README.md` (과거 상세 이력)

## 3. Document Roles
1. `CONTEXT_MIN`: 최소 컨텍스트 요약
2. `DECISIONS`: 현재 유효한 결정만 유지
3. `PLAN_LIVING_HYBRID`: 현재 실행 계획/단계 상태
4. `TASKS_MINIMUM_UNITS`: 활성 태스크 보드
5. `archive/*`: 무손실 상세 이력 원장

## 4. Update Rules
1. 정책 변경: `DECISIONS` 우선 갱신
2. 우선순위/단계 변경: `PLAN` + `TASKS` 동기화
3. 부채 생성/해소: `TECH_DEBT_REGISTER` 갱신
4. 상세 이력 추가: `archive/*` append
