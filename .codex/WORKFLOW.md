# WORKFLOW.md
Authoritative for: execution sequence for non-trivial work.

## Default Flow
1) Analyze
2) Discuss/Critique
3) Patch
4) Verify

For high-risk tasks, use multiple turns and make the stage explicit.

## Stage Requirements
### 1) Analyze
- Restate objective.
- Identify constraints from `CONTEXT.md` and `RULES.md`.
- List missing variables.

### 2) Discuss/Critique
- Challenge assumptions.
- Identify failure modes and edge cases (`RISK.md`).
- Choose the lowest-risk path.
- Check practical operability in current environment before tool/design adoption.

### 3) Patch
- Keep changes minimal and scoped (`R6`, `R7`).
- No speculative redesign.

### 4) Verify
- Provide evidence (`VERIFY.md`).
- Report what was verified and what was not.
- Capture key learning from failures or near-misses for next iteration.

## When It Is OK to Go Fast
You may collapse Analyze+Discuss only if task is trivial, low-risk, and local.
Verification is never skipped.

## Language Rule
Frame outputs as best-effort proposals requiring validation in practice.
