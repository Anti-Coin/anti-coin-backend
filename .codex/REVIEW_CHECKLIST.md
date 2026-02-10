# REVIEW_CHECKLIST.md
Authoritative for: pre-merge and pre-apply review gate.

## Stop If Any Critical Item Fails
### Critical
- [ ] One clear purpose (`R6`)
- [ ] Small and reviewable scope (`R7`) or approved exception
- [ ] Stability is preserved/improved (`R1`, `R2`)
- [ ] Data/time correctness is maintained (`R3`, `R4`, `R5`)
- [ ] Verification evidence exists (`R10`, `VERIFY.md`)
- [ ] Regression test exists for bug fix or defer reason is documented
- [ ] Risk/corner cases are disclosed (`RISK.md`)

### Warning
- [ ] Added complexity is justified
- [ ] Dependency/tool impact is justified (`R8`, `R9`)
- [ ] Rollback/recovery is clear

## Final Gate
If this fails at 3 a.m., can an operator diagnose cause quickly?
If no, do not approve yet.
