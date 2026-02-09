# RISK.md
Authoritative for: mandatory risk disclosure on non-trivial changes.

## Required Sections
Every non-trivial proposal must include:
1) Uncertainty statement
2) Failure modes
3) Corner cases
4) Mitigation or detection plan

Without these, proposal is incomplete.

## Typical Risk Categories
- Resource (CPU/RAM/disk/log growth)
- Data (duplication/corruption/idempotency/timezone)
- Time/scheduling (drift, delay, overlap)
- Failure/recovery (restart loops, retry storms)
- External dependencies (API limits/outage/schema drift)
- Observability (silent failure, noisy or missing alerts)

## Baseline Stance
Treat all proposals as best-effort hypotheses that require real validation.
