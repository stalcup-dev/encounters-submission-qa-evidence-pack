# Encounters Submission QA SOP v0.1
**Scope:** Synthetic, PHI-free **tabular encounter-style QA, not an EDI parser**.  
**Applies to:** Adjudicated claims data ("Encounters") preparation, validation, submission support, remediation via reprocessing, submissions tracking, UAT evidence, and RCA-lite documentation across vendors and LOB/markets.

**Scenario (public-safe):** HarborPoint Health Plan receives weekly encounter batches from delegated vendors for multiple lines of business (e.g., Medicaid and Commercial). Before submitting these encounters to external reporting endpoints (state/federal programs), the Encounters team must catch blocking defects, prioritize remediation, and document a defensible audit trail.

This evidence pack simulates that workflow end-to-end:
- Row-level rejects (missing member/provider fields, invalid dates, eligibility outside coverage, duplicates, etc.)
- Batch-level flags when operational thresholds are exceeded (duplicate rate >1%, eligibility mismatch >2%, volume shift >15%)
- Ops decisions: Hold / Reprocess / Submit-with-monitoring
- UAT traceability for upgrades and vendor feed changes

Out of scope: This is not provider billing QA and not an EDI/837 parser; it's tabular pre-submit QA for payer encounter reporting.

## 1) Purpose
Provide an operations-ready standard process to:
- prepare encounter batches,
- run repeatable pre-submit validation,
- triage by severity and business impact,
- support submission and response intake,
- manage remediation/reprocessing cycles,
- document evidence for UAT and RCA.

Primary output artifacts:
- `/outputs/rejects.csv`
- `/outputs/triage_summary.csv`
- `/outputs/submission_tracker_template.csv` (submission/remediation tracking)
- `/docs/metric_definitions.md` (metric formulas, grains, and thresholds)
- `/outputs/screenshots/top_rejects.png`
- `/outputs/screenshots/triage_trend.png`
- `/docs/Encounters_QA_Report.html`

## 2) Pre-Submit Checklist
Run before each submission window:
1. Confirm input readiness for all active vendors and LOB/markets (`MEDICAID`, `COMMERCIAL`).
2. Confirm reference data is current (members, providers) for the run period.
3. Execute validation workflow to generate:
   - row-level and batch-level rejects in `/outputs/rejects.csv`
   - weekly triage aggregation in `/outputs/triage_summary.csv`
4. Confirm anomaly checks present in rejects and triage:
   - `DUP_RATE_GT_1PCT`
   - `ELIG_MISMATCH_GT_2PCT`
   - `VOLUME_SHIFT_GT_15PCT`
5. Confirm metric math uses canonical definitions in `/docs/metric_definitions.md`:
   - numerator and denominator are correct
   - grain matches the intended output artifact
   - thresholds use strict greater-than (`>`) where specified
6. Review visual evidence:
   - `/outputs/screenshots/top_rejects.png`
   - `/outputs/screenshots/triage_trend.png`
7. Update tracker (`/outputs/submission_tracker_template.csv`) with current run status and ownership.

## 3) Decision Table
| Severity/Signal | Operational Rule | Required Action |
|---|---|---|
| `BLOCKER` > 0 | Submission gate fails | Do not submit. Assign remediation and reprocess before revalidation. |
| `HIGH` batch flags (`DUP_RATE_GT_1PCT`, `ELIG_MISMATCH_GT_2PCT`) | Elevated risk for submission quality | Remediate and reprocess impacted batch; revalidate prior to submit/resubmit. |
| `MONITOR` (`VOLUME_SHIFT_GT_15PCT`, `FINANCIAL`, `CODE_SET`) | Submission may proceed with controls | Submit if no BLOCKER/HIGH blockers remain; trend weekly and capture RCA-lite notes. |

## 4) Remediation Workflow Loop
Canonical operating loop:
1. Preparation (batch build and readiness checks).
2. Validation (automated QA to produce rejects + triage).
3. Review (prioritize `BLOCKER` then `HIGH`, then `MONITOR` trends).
4. Submission (state/federal agency handoff).
5. Intake (ack/reject response capture).
6. Remediation assignment (vendor/IT/ops owner).
7. Reprocessing (targeted fixes and batch regeneration).
8. Revalidation (rerun QA outputs).
9. Resubmission (when gates pass).
10. Close (status closure + RCA-lite summary + evidence links).

## 5) Tracker Usage and Cadence
Use `/outputs/submission_tracker_template.csv` as the source of operational truth for submissions tracking.

Minimum fields to maintain each cycle:
- `batch_id, submit_date, agency, lob, vendor, claims_in_batch`
- `rejects_total, blockers, high, monitor`
- `status, owner, sla_due, rerun_date, notes`

Cadence:
1. Pre-submit checkpoint: update counts/owner/status after validation.
2. Daily operations checkpoint (or each intake event): update status and SLA.
3. Post-remediation checkpoint: record rerun date and revalidation outcome.
4. Closeout checkpoint: mark closed with RCA-lite notes and evidence links.

## 6) UAT and RCA Expectations
- UAT evidence aligns rule logic, test cases, and artifacts in project docs.
- Every significant defect follows RCA-lite:
  repro -> expected vs actual -> suspected root cause -> fix -> retest evidence.
- Keep traceability between validation outputs and operational decisions for auditability.

## 7) Explicit Boundaries
This SOP governs **tabular encounter-style QA** and operations workflow.  
It **does not** parse or validate EDI/837 transaction syntax.

## 8) Quick Start (Contract-Locked Repro)
Run from repo root:

```powershell
.\.venv\Scripts\Activate.ps1
```

```powershell
python src/generate_dataset.py --seed 42 --run_date 2026-05-10 --out_dir .
python src/verify_dataset.py --run_date 2026-05-10
python src/verify_outputs.py
python src/verify_report_html.py
powershell -ExecutionPolicy Bypass -File scripts/export_reports.ps1 -SkipPdf
```
