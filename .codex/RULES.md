# RULES.md
Authoritative for: non-negotiable constraints.

## Priority Order
Always decide in this order:
1) Stability
2) Cost/resource efficiency
3) Performance

## Core Rules
### R1) Stability over cleverness
Prefer explicit, predictable, debuggable behavior.

### R2) No silent failure
Do not swallow errors. Log clearly. Alert when correctness/freshness is impacted.

### R3) Idempotency first
Retries and reruns must not corrupt data or produce inconsistent artifacts.

### R4) UTC internally
Use UTC for internal time. Convert only at boundaries (UI/output if needed).

### R5) Freshness honesty
Do not serve stale/invalid data as fresh. Degrade explicitly (for example, 503).

### R6) One task, one purpose
Do not mix unrelated concerns in one task.

### R7) Small patch default
Avoid large one-shot changes from AI.
Default budget: around 200 lines diff and at most 3 files per task unless approved.

### R8) Heavy tools are conditional
Do not introduce heavy orchestration (Airflow, MLflow, similar) by default.
Required to propose:
- problem solved
- Free Tier cost (CPU/RAM/disk/ops)
- minimal alternative
- rollback plan

### R9) Dependency gate
New dependency requires rationale, ops cost, alternative, and rollback.

### R10) Verification is mandatory
A task is not done without test/manual/runtime evidence (`VERIFY.md`).

### R11) Practical MVP over theoretical perfection
Prefer the smallest operable solution that satisfies reliability guardrails.
Do not introduce complexity just to make the design look complete on paper.

## Conflict Handling
- If rules conflict, escalate instead of guessing.
- This file overrides all `.codex` docs.
- If a user request conflicts with these rules, explain and request explicit override.
