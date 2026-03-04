# UAT Test Plan - Encounters QA Lab (GCT-090)

## Objective
Validate that encounter-style QA outputs support pre-submit operations and remediation decisions using synthetic, PHI-free data. Coverage includes row-level rules R001-R015 and batch anomaly rules R901-R903.

## Scope
- In scope: `/outputs/rejects.csv`, `/outputs/triage_summary.csv`, anomaly conventions, and evidence generation under `/outputs/uat/<test_id>/...`.
- Out of scope: EDI transaction parsing/validation (837/834 syntax).

## Assumptions
- Dataset already generated from GCT-020 with incident story map.
- Validation outputs generated from `notebooks/01_validate.ipynb` and pass `src/verify_outputs.py`.

## Entry Criteria
- Required files exist: `outputs/rejects.csv`, `outputs/triage_summary.csv`, `outputs/story_map.csv`.
- Dataset/outputs verifiers pass.

## Exit Criteria
- 17/17 tests pass.
- Every rule_id R001-R015 and R901-R903 is covered with evidence artifacts.
- Defects (if any) logged using `/docs/defect_triage_template.md`.

## Test Catalog (17 executable tests)
| test_id | rule_id(s) | expected rows in rejects | expected impact in triage_summary | evidence path |
|---|---|---|---|---|
| UAT-001 | R001_NULL_MEMBER_ID | `reject_code=NULL_MEMBER_ID` present (expected 10) | `REQUIRED_FIELD/BLOCKER` present | `/outputs/uat/UAT-001/` |
| UAT-002 | R002_NULL_CLAIM_ID | `reject_code=NULL_CLAIM_ID` present (expected 5), header-level rows | `REQUIRED_FIELD/BLOCKER` present | `/outputs/uat/UAT-002/` |
| UAT-003 | R003_NULL_PROVIDER_NPI | `reject_code=NULL_PROVIDER_NPI` present (expected 10) | `REQUIRED_FIELD/BLOCKER` present | `/outputs/uat/UAT-003/` |
| UAT-004 | R004_NULL_SERVICE_FROM | `reject_code=NULL_SERVICE_FROM` present (expected 5) | `REQUIRED_FIELD/BLOCKER` present | `/outputs/uat/UAT-004/` |
| UAT-005 | R005_NPI_BAD_LENGTH | `reject_code=NPI_BAD_LENGTH` present (expected 10) | `PROVIDER/BLOCKER` present | `/outputs/uat/UAT-005/` |
| UAT-006 | R006_NPI_NOT_NUMERIC | `reject_code=NPI_NOT_NUMERIC` present (expected 10) | `PROVIDER/BLOCKER` present | `/outputs/uat/UAT-006/` |
| UAT-007 | R007_NPI_NOT_FOUND | `reject_code=NPI_NOT_FOUND` present (expected 10) | `PROVIDER/BLOCKER` present | `/outputs/uat/UAT-007/` |
| UAT-008 | R008_SERVICE_TO_BEFORE_FROM | `reject_code=SERVICE_TO_BEFORE_FROM` present (expected 10) | `DATES/BLOCKER` present | `/outputs/uat/UAT-008/` |
| UAT-009 | R009_FUTURE_SERVICE_DATE | `reject_code=FUTURE_SERVICE_DATE` present (expected 10) | `DATES/BLOCKER` present | `/outputs/uat/UAT-009/` |
| UAT-010 | R010_SERVICE_OUTSIDE_COVERAGE | `reject_code=SERVICE_OUTSIDE_COVERAGE` present (expected 6) | `MEMBER_ELIGIBILITY/HIGH` present | `/outputs/uat/UAT-010/` |
| UAT-011 | R011_DUP_CLAIM_KEY | `reject_code=DUP_CLAIM_KEY` present (expected 10 rows from 5 dup keys) | `DUPLICATE/HIGH` present | `/outputs/uat/UAT-011/` |
| UAT-012 | R012_PAID_GT_ALLOWED | `reject_code=PAID_GT_ALLOWED` present (expected 40) | `FINANCIAL/MONITOR` present | `/outputs/uat/UAT-012/` |
| UAT-013 | R013_ALLOWED_GT_CHARGE | `reject_code=ALLOWED_GT_CHARGE` present (expected 40) | `FINANCIAL/MONITOR` present | `/outputs/uat/UAT-013/` |
| UAT-014 | R014_NULL_PROC + R015_NULL_DX | `reject_code IN (NULL_PROC,NULL_DX)` present (expected 20 each) | `CODE_SET/MONITOR` present | `/outputs/uat/UAT-014/` |
| UAT-015 | R901_DUP_RATE_GT_1PCT | batch anomaly row present; enforce `claim_id=BATCH::<batch_id>`, `line_id` blank, `service_from` blank | `DUPLICATE/HIGH` anomaly impact present | `/outputs/uat/UAT-015/` |
| UAT-016 | R902_ELIG_MISMATCH_GT_2PCT | batch anomaly row present; enforce batch row convention | `MEMBER_ELIGIBILITY/HIGH` anomaly impact present | `/outputs/uat/UAT-016/` |
| UAT-017 | R903_VOLUME_SHIFT_GT_15PCT | batch anomaly row present; enforce batch row convention | `VOLUME_ANOMALY/MONITOR` anomaly impact present | `/outputs/uat/UAT-017/` |

## Execution Method
Run `notebooks/03_uat.ipynb` (or execute via nbconvert). Notebook runs verifiers, executes assertions, and writes test artifacts to:
- `/outputs/uat/<test_id>/rejects.csv`
- `/outputs/uat/<test_id>/triage_summary.csv`
- `/outputs/uat/<test_id>/run_log.txt`

## Evidence Capture
- Per-test artifacts: `/outputs/uat/<test_id>/...`
- Cross-reference: `/docs/traceability_matrix.csv`
- Defect logging template: `/docs/defect_triage_template.md`
