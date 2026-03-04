# Defect Triage Template (RCA-lite)

## Defect Header
- Defect ID:
- Date logged:
- Logged by:
- Test ID(s):
- Rule ID(s):
- Severity:
- Status:

## Repro Context
- Dataset version / receipt reference:
- Environment / command executed:
- Steps to reproduce:

## Expected vs Actual
- Expected result:
- Actual result:

## RCA-lite Classification
Select one primary and optional secondary categories:
- `JOIN`: join grain/key mismatch, duplicate expansion, missing join coverage.
- `NULL_HANDLING`: null/blank normalization issue, unexpected null propagation.
- `KEY_LOGIC`: claim_key or business key construction issue.
- `DATE_LOGIC`: week derivation, service date logic, coverage window logic.
- `THRESHOLD_CALC`: rate/denominator/median threshold computation issue.
- `REF_DATA`: reference members/providers integrity or lookup gap.

## Suspected Root Cause
- Primary category:
- Technical cause hypothesis:
- Impacted outputs:

## Fix Plan
- Proposed fix:
- Owner:
- ETA:

## Retest Evidence
- Retest date:
- Retest command(s):
- Evidence artifacts (paths):
  - `/outputs/uat/<test_id>/rejects.csv`
  - `/outputs/uat/<test_id>/triage_summary.csv`
  - `/outputs/uat/<test_id>/run_log.txt`
- Result (Pass/Fail):

## Closure Notes
- Final root cause:
- Preventive action:
