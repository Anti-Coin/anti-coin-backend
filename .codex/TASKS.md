# TASKS.md
Authoritative for: task boundaries and execution discipline.

## Task Definition
A task is valid only if it has:
- one clear purpose
- independent reviewability
- safe rollback

If not, split it.

## Hard Boundaries
- One task, one purpose (`R6`).
- Small patch default (`R7`): around 200 lines and up to 3 files unless approved.
- Do not mix safety fixes, refactors, and optimizations in one task.
- Do not ask AI for large one-shot code output.

## Required Lifecycle
1) Plan: objective, scope, files, assumptions, risks.
2) Test Design: failure scenarios and expected guardrails.
3) Patch: minimal focused changes.
4) Verify: evidence of correctness and non-regression (`VERIFY.md`).

## Test Requirement
- Bug fix task should include a regression test by default.
- New behavior task should include at least one positive and one failure-path test.
- If test is deferred, record reason and follow-up task ID.

## If Complexity Expands Mid-Task
- Stop scope growth.
- Document discovery.
- Propose follow-up task(s).
