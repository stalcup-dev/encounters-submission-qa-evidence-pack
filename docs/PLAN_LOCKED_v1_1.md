# GCT-000 - Contract Lock v1.1 (No Drift)

**Owner:** Codex  
**Goal:** Write locked clarifications into a single execution contract.  
**Deliverable:** `/docs/PLAN_LOCKED_v1_1.md`

## Scope and Authority
This document is the authoritative lock for execution behavior in v1.1. If any code, notebook, or prior doc conflicts with this contract, this contract wins until a versioned replacement is approved.

## Global Locks
- `RUN_DATE` is locked to `2026-05-10`.
- `RUN_DATE` is global and MUST remain after the latest `service_to` used in the run.
- `batch_id` format is locked to `BATCH_<YYYYMMDD>_<VENDOR>_<LOB>_W<NN>`.

## Locked Definitions
1. **R903 volume metric**
- R903 volume uses `COUNT(*)` `encounters_header` rows per `batch_id`.
- `claims_in_batch` is row-count volume at header grain for the target batch.

2. **Duplicate construction and participation**
- Pick exactly 5 clean claims.
- Clone each once with a new `claim_id` and the same `claim_key`.
- Remove 5 other claims (not the cloned rows) so final batch size remains 200.
- Duplicate participation is locked to `10/200`.

3. **Money precision and `claim_key` consistency**
- Enforce one safe rule globally:
- Option A: store money as integer cents internally; or
- Option B: apply `ROUND(x,2)` everywhere before CSV writes and before computing `claim_key`.
- No mixed precision path is allowed for fields contributing to output or `claim_key`.

4. **Batch anomaly `week_start` derivation**
- Batch anomaly rows MUST have `service_from = null`.
- In triage, `week_start` MUST be derived by parsing `YYYYMMDD` from `batch_id`.
- Derivation source is `batch_id` for all rows (row-level rejects and batch-anomaly rejects).
- `service_from` MUST NOT be used as the primary bucketing field for triage week assignment.
- `W<NN>` is an ordinal label only and MUST NOT be used to derive `week_start`.

## No-Drift Clause
- These locks are fixed for v1.1 and are not to be reinterpreted during implementation or QA.
- Any change requires explicit version bump and replacement contract (v1.2+).
