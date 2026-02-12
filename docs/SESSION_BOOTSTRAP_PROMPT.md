# Session Bootstrap Prompt (for New Chat)

아래 텍스트를 새 세션 시작 메시지로 사용:

```
다음 문서를 순서대로 읽고 현재 상태를 요약해줘.
1) docs/CONTEXT_MIN.md
2) docs/PROJECT_IDENTITY.md
3) docs/OPERATING_CONSTRAINTS.md
4) docs/DECISIONS.md
5) docs/PLAN_LIVING_HYBRID.md
6) docs/TASKS_MINIMUM_UNITS.md
7) docs/TECH_DEBT_REGISTER.md
8) docs/SESSION_HANDOFF.md

필요할 때만 docs/archive/README.md를 통해 특정 원문 이력을 추가로 확인해줘.

요약 형식:
- 철학과 도메인 정책 분리 요약(5~10줄)
- 현재 최우선 Task 1개
- 다음 후보 Task 2개
- 이번 작업 리스크 3개
- 실행 전 확인 질문(필요한 경우만)
```

운용 규칙:
1. 요약 이후 바로 코드 변경하지 않고, 먼저 합의한다.
2. 합의 후에는 한 번에 한 Task만 진행한다.
