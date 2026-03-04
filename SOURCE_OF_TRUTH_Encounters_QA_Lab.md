# SOURCE OF TRUTH (SoT) — Encounters Submission QA Lab (Synthetic, PHI-free) v0.2
**Last updated:** 2026-02-28  
**Project:** 24-hour portfolio build to signal fit for **Business Analyst – Encounters (Remote)** in a public-safe payer context (HarborPoint Health Plan scenario)

---

## 0) One-line intent
Prove I can run the **Encounters submission QA + triage + remediation tracking + SOP + UAT evidence** loop using **synthetic, PHI-free** data (tabular encounter-style validation — **not** an EDI/837 parser).

---

## 1) Success criteria (hire-signal)
A reviewer should be able to answer “yes” to all of these:

1. **Pre-submit validation exists:** repeatable checks generate `rejects.csv` + `triage_summary.csv`.
2. **Ops-ready triage exists:** rejects classified by **category / code / severity**, aggregated by **week + LOB + vendor**.
3. **Remediation workflow is operationalized:** a submission/remediation tracker exists with status + owner + SLA.
4. **Documentation exists:** a 1-page runbook (SOP) describes the end-to-end workflow in encounters ops language.
5. **UAT evidence exists:** a UAT plan + 12–18 tests + traceability matrix + defect triage template.
6. **README proves relevance:** “what this is / how to run / what outputs / what it proves for Encounters BA” + 2 screenshots.

---

## 2) Constraints (non-negotiable)
- **PHI-free** synthetic data only.
- **No real 837/834 parsing.** This is encounter-style **tabular** validation + ops workflow.
- Shippable in **24 hours** using coding agents.

---

## 3) Must-ship deliverables (paths are binding)
### Docs
- `/docs/runbook_v0_1.md`  *(1-page SOP)*
- `/docs/uat_test_plan.md`
- `/docs/defect_triage_template.md`
- `/docs/traceability_matrix.csv`
- `/docs/resume_bullets.md` *(optional but recommended)*

### Outputs
- `/outputs/rejects.csv`
- `/outputs/triage_summary.csv`
- `/outputs/submission_tracker_template.csv` *(or `.xlsx`)*
- `/outputs/screenshots/top_rejects.png`
- `/outputs/screenshots/triage_trend.png`

### Repo layout
- `/data_raw` (synthetic CSVs)
- `/sql` (validation queries) **or** `/src` (python validation runner) — either is fine
- `/src` (generator + runner if using Python)
- `/outputs`
- `/docs`
- `README.md`

---

## 4) Data model (synthetic tables)
### `encounters_header.csv`
`batch_id, claim_id, member_id, provider_npi, lob, vendor, service_from, service_to, total_charge, total_allowed, total_paid, adjudication_date`

### `encounters_lines.csv`
`claim_id, line_id, proc_code, dx_code, units, charge, allowed, paid`

### `reference_members.csv`
`member_id, dob, gender, coverage_start, coverage_end`

### `reference_providers.csv`
`provider_npi, provider_name, taxonomy`

---

## 5) Output specs (binding)
### 5.1 `rejects.csv` (row-level + batch-level anomalies)
Columns:
`claim_id, line_id, batch_id, lob, vendor, service_from, reject_category, reject_code, severity, detected_ts`

Schema note (binding):
- `rejects.csv` output schema is **10 columns** and **does not include `rule_id` by design**.
- `rule_id` is an **internal/intermediate** field used for validation traceability, UAT joins, and traceability matrix mapping.
- Export behavior is intentional: **`COPY TO` intentionally drops `rule_id`** during final `rejects.csv` projection (this is not truncation).

**Row-level rejects**
- `claim_id` = actual claim_id
- `line_id` = actual line_id or null if header-level
- `service_from` populated when applicable

**Batch-level anomaly rows (PATCHED — removes ambiguity)**
- Represent batch anomalies **in the same `rejects` schema** with:
  - `line_id = null`
  - `claim_id = "BATCH::<batch_id>"` (canonical convention)
  - `service_from = null`
  - Category mapping: `R901 -> DUPLICATE`, `R902 -> MEMBER_ELIGIBILITY`, `R903 -> VOLUME_ANOMALY`

### 5.2 `triage_summary.csv`
Columns:
`week_start, lob, vendor, reject_category, severity, reject_count, affected_claims`

---

## 6) Reject taxonomy (canonical)
### 6.1 Categories (do not change)
- REQUIRED_FIELD
- PROVIDER
- MEMBER_ELIGIBILITY
- DATES
- FINANCIAL
- DUPLICATE
- CODE_SET
- VOLUME_ANOMALY *(batch-level)*

### 6.2 Severity model (PATCHED — row vs batch clarified)
- **Row-level rejects:**
  - REQUIRED_FIELD = **BLOCKER**
  - PROVIDER (format/ref failures) = **BLOCKER**
  - DATES (invalid/future) = **BLOCKER**
  - MEMBER_ELIGIBILITY = **HIGH**
  - DUPLICATE = **HIGH**
  - FINANCIAL / CODE_SET = **MONITOR** (unless escalated later)
- **Batch-level threshold checks** emit **batch anomaly rows** (in `rejects.csv`) when batch rate exceeds thresholds:
  - `DUP_RATE_GT_1PCT` (HIGH) when duplicate rate > 1.0%
  - `ELIG_MISMATCH_GT_2PCT` (HIGH) when eligibility mismatch rate > 2.0%

### 6.3 Operational thresholds
- Duplicate rate HIGH if **> 1.0%** of claims_in_batch
- Eligibility mismatch HIGH if **> 2.0%** of claims_in_batch
- Volume shift investigate if **> 15%** vs trailing 8-week median

---

## 7) Canonical rule ID system (binds code + UAT + traceability)
**Rule ID format:** `R###_<UPPER_SNAKE_NAME>`

### 7.1 MVP rule catalog (must implement)
| rule_id | reject_category | reject_code | severity | description |
|---|---|---|---|---|
| R001_NULL_MEMBER_ID | REQUIRED_FIELD | NULL_MEMBER_ID | BLOCKER | member_id missing on header |
| R002_NULL_CLAIM_ID | REQUIRED_FIELD | NULL_CLAIM_ID | BLOCKER | claim_id missing/blank |
| R003_NULL_PROVIDER_NPI | REQUIRED_FIELD | NULL_PROVIDER_NPI | BLOCKER | provider_npi missing on header |
| R004_NULL_SERVICE_FROM | REQUIRED_FIELD | NULL_SERVICE_FROM | BLOCKER | service_from missing |
| R005_NPI_BAD_LENGTH | PROVIDER | NPI_BAD_LENGTH | BLOCKER | provider_npi not 10 digits |
| R006_NPI_NOT_NUMERIC | PROVIDER | NPI_NOT_NUMERIC | BLOCKER | provider_npi contains non-numeric |
| R007_NPI_NOT_FOUND | PROVIDER | NPI_NOT_FOUND | BLOCKER | provider_npi not in reference_providers |
| R008_SERVICE_TO_BEFORE_FROM | DATES | SERVICE_TO_BEFORE_FROM | BLOCKER | service_to < service_from |
| R009_FUTURE_SERVICE_DATE | DATES | FUTURE_SERVICE_DATE | BLOCKER | service dates in the future |
| R010_SERVICE_OUTSIDE_COVERAGE | MEMBER_ELIGIBILITY | SERVICE_OUTSIDE_COVERAGE | HIGH | service dates outside coverage window |
| R011_DUP_CLAIM_KEY | DUPLICATE | DUP_CLAIM_KEY | HIGH | duplicate claim key within batch |
| R012_PAID_GT_ALLOWED | FINANCIAL | PAID_GT_ALLOWED | MONITOR | paid > allowed (header or line) |
| R013_ALLOWED_GT_CHARGE | FINANCIAL | ALLOWED_GT_CHARGE | MONITOR | allowed > charge |
| R014_NULL_PROC | CODE_SET | NULL_PROC | MONITOR | proc_code missing on a line |
| R015_NULL_DX | CODE_SET | NULL_DX | MONITOR | dx_code missing on a line |

Duplicate `claim_key` (R011) is defined as: `(batch_id, member_id, provider_npi, service_from, total_charge)`. Duplicates are detected within the same `batch_id` only.

### 7.2 Batch anomaly rule catalog (must implement)
| rule_id | reject_category | reject_code | severity | description |
|---|---|---|---|---|
| R901_DUP_RATE_GT_1PCT | DUPLICATE | DUP_RATE_GT_1PCT | HIGH | duplicate rate > 1.0% of claims_in_batch (emit batch row) |
| R902_ELIG_MISMATCH_GT_2PCT | MEMBER_ELIGIBILITY | ELIG_MISMATCH_GT_2PCT | HIGH | eligibility mismatch rate > 2.0% of claims_in_batch (emit batch row) |
| R903_VOLUME_SHIFT_GT_15PCT | VOLUME_ANOMALY | VOLUME_SHIFT_GT_15PCT | MONITOR | computed weekly at grain (lob, vendor): compare current week claim volume vs trailing 8-week median for same (lob, vendor); emit batch anomaly when deviation >15% |

> SME additional MONITOR anomalies (reject-rate spike, LOB mix shift, vendor pattern shift) are **optional stretch** and must live under `/optional` if added.

---

## 8) Operational workflow (runbook-aligned)
Canonical ops loop:
1) Preparation (batch build)  
2) Pre-submit validation (automated QA → `rejects` + `triage_summary`)  
3) Ops review (BLOCKER first, then HIGH, then MONITOR trends)  
4) Submission (state/federal agency) + tracker update  
5) Response/reject intake + tracker update  
6) Remediation assignment (vendor/IT/ops)  
7) Reprocess (regenerate batch)  
8) Revalidate  
9) Resubmit  
10) Close + RCA-lite notes

---

## 9) Submission & remediation tracker (required fields)
Template fields:
`batch_id, submit_date, agency, lob, vendor, claims_in_batch, rejects_total, blockers, high, monitor, status, owner, sla_due, rerun_date, notes`

Status values:
`PREP, VALIDATED, SUBMITTED, REJECTED, REPROCESSING, RESUBMITTED, CLOSED`

---

## 10) UAT evidence pack (required)
### 10.1 UAT test plan
Must include:
- objective, scope, assumptions
- synthetic error injection approach
- entry/exit criteria
- evidence capture locations (outputs + screenshots)

### 10.2 Test cases (target: 16–17)
- Must include happy path + negative tests + batch anomaly tests for:
  - R901_DUP_RATE_GT_1PCT
  - R902_ELIG_MISMATCH_GT_2PCT
  - R903_VOLUME_SHIFT_GT_15PCT
- Every test references **canonical rule_id**s (R###).

### 10.3 Traceability matrix
Columns:
`requirement, rule_id, test_ids, artifact_path`

### 10.4 Defect triage template
Must include RCA-lite fields:
repro → expected vs actual → suspected root cause → fix → retest evidence

---

## 11) Measurement capture (fill during execution)
- Dataset size: `[CLAIMS]` claims, `[LINES]` lines, `[BATCHES]` batches
- Reject mix: overall reject rate + top 3 categories
- Ops impact: review time saved (even if estimated)
- Remediation: # cycles or first-pass “VALIDATED with no BLOCKERS” rate
- Testing: `[N_RULES]` rules, `[N_TESTS]` UAT tests executed

---

## 12) Language to mirror (posting keywords)
preparation, validation, submission, adjudicated claims data (“Encounters”), state/federal agencies, remediation via reprocessing, operational expertise, documentation (SOPs), submissions tracking, UAT, RCA, vendors, LOB/markets

---

## Appendix A — SME reject codes (optional expansion)
If time allows (after MVP ships), add these as **MONITOR** or optional checks:
- PROVIDER_TAXONOMY_MISSING
- HEADER_LINE_TOTAL_MISMATCH (tolerance-based)
- DUP_HEADER_RECORD / DUP_LINE_RECORD
- PROC_INVALID_FORMAT / DX_INVALID_FORMAT
- REJECT_RATE_SPIKE / LOB_DISTRIBUTION_SHIFT / VENDOR_PATTERN_SHIFT

**Rule:** Optional items must not change the required outputs or schemas.

