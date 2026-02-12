# STARTUP_PROTOCOL.md
Authoritative for: first-read order and alignment checks at session start.

## Required Read Order (Token-aware)
1) `docs/README.md`
2) `docs/CONTEXT_MIN.md`
3) `docs/PROJECT_IDENTITY.md`
4) `docs/OPERATING_CONSTRAINTS.md`
5) `docs/DECISIONS.md`
6) `docs/PLAN_LIVING_HYBRID.md`
7) `docs/TASKS_MINIMUM_UNITS.md`
8) `docs/TECH_DEBT_REGISTER.md`
9) `docs/SESSION_HANDOFF.md`

## Optional Deep Read (Only If Needed)
1) `docs/ENGINEERING_CONSTITUTION.md`
2) `docs/TEST_STRATEGY.md`
3) `docs/archive/README.md` and specific archive files

## Mandatory Output Before Coding
Provide:
1) Philosophy summary (owner principles)
2) Domain policy summary (separate from philosophy)
3) One current task recommendation
4) Top 3 current risks

## Guardrail
If philosophy and domain policy are mixed, pause and correct before patching.
