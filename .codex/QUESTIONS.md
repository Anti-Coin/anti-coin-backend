# QUESTIONS.md
Authoritative for: when to ask first vs proceed.

## Ask First If Any Critical Variable Is Missing
- Runtime/deployment assumption
- Failure policy (retry/stop/alert/degrade)
- Boundary between philosophy and domain policy
- Data contract (schema/timezone/freshness/idempotency)
- Definition of done and non-regression target
- Verification method

If any item above is unclear, ask before code.

## Proceed Without Blocking Questions Only When
- Scope is explicit and local.
- Change is mechanical and low risk.
- Verification is obvious.

Then proceed with explicit assumptions.

## Question Quality
- Ask only what can change correctness/safety.
- Prefer concrete, answerable prompts.
- Avoid broad exploratory questions.

## Anti-Patterns
- Hidden assumptions.
- Over-questioning trivial tasks.
- Skipping questions on high-risk tasks.
