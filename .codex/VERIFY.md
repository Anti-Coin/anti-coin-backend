# VERIFY.md
Authoritative for: acceptance evidence.

## Done Means Verified
Compilation is not completion. Completion requires verification evidence (`R10`).

## Minimum Requirement
Each non-trivial task must include at least one:
- automated test
- manual verification steps
- runtime evidence (logs/metrics/artifacts)

If not possible, explain why and state residual risk.

## TDD-Oriented Rule
When practical:
1) write failing test first (or in same patch with explicit failure scenario),
2) implement minimal fix,
3) keep regression test permanent.

For bug fixes, absence of regression test must be justified.

## Required Coverage (as applicable)
1) Functional correctness
2) Stability/runtime safety
3) Data integrity and idempotency
4) Failure/degradation behavior
5) Observability

## Reporting Format
- Verified:
- Method:
- Not verified:
- Remaining assumptions/risks:
