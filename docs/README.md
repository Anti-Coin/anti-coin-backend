# Coin Predict Documentation Index

- Last Updated: 2026-02-20
- Purpose: 새 세션에서 최소 토큰으로 정렬하고, 필요 시에만 깊게 읽기
- Active Doc Density Policy: Phase B는 요약 유지, Phase C/D는 실행 기준/리스크/검증 정보를 상세 유지

## 1. Fast Read Order (Default)
1. `docs/CONTEXT_MIN.md`
2. `docs/PROJECT_IDENTITY.md`
3. `docs/OPERATING_CONSTRAINTS.md`
4. `docs/DECISIONS.md`
5. `docs/PLAN_LIVING_HYBRID.md`
6. `docs/TIMEFRAME_POLICY_MATRIX.md`
7. `docs/TASKS_MINIMUM_UNITS.md`
8. `docs/TECH_DEBT_REGISTER.md`
9. `docs/SESSION_HANDOFF.md`

## 2. Deep Read (When Needed)
1. `docs/ENGINEERING_CONSTITUTION.md`
2. `docs/TEST_STRATEGY.md`
3. `docs/GLOSSARY.md`
4. `docs/archive/README.md`

## 3. Document Roles
1. `CONTEXT_MIN`: 최소 컨텍스트 요약
2. `DECISIONS`: 현재 유효한 결정 요약 + 최신 상세 결정
3. `PLAN_LIVING_HYBRID`: 현재 실행 계획/단계 상태
4. `TIMEFRAME_POLICY_MATRIX`: timeframe 정책 매트릭스
5. `TASKS_MINIMUM_UNITS`: 활성 태스크 보드
6. `DISCUSSION`: 구현 전 쟁점/옵션/근거 토론 로그
7. `archive/*`: 무손실 상세 이력 원장

## 4. Update Rules
1. 정책 변경: `DECISIONS` 우선 갱신
2. 우선순위/단계 변경: `PLAN` + `TASKS` 동기화
3. 부채 생성/해소: `TECH_DEBT_REGISTER` 갱신
4. 구현 전 쟁점 정리: `DISCUSSION` 갱신
5. 상세 이력 추가: `archive/*` append
