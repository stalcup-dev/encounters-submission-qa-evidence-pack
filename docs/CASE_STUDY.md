# Encounters Submission QA Evidence Pack — HarborPoint Health Plan

*A hiring manager case study by the project owner.*

---

## TL;DR

- **What:** A reproducible, end-to-end QA system that validates weekly encounter batches before they are submitted to state and federal reporting endpoints — built for a fictional payer, HarborPoint Health Plan.
- **Why it matters:** Encounter submissions that carry blocking defects can be rejected by downstream agencies, triggering financial penalties and compliance findings; this system catches those defects before they leave the plan.
- **How it works:** Automated row-level validation generates `outputs/rejects.csv`; batch-level anomaly rules fire when operational thresholds are breached; a triage layer (`outputs/triage_summary.csv`) classifies every issue by severity so the ops team knows what to hold, reprocess, or monitor.
- **Evidence:** A 10-week synthetic story (W02 through W10) demonstrates the full incident lifecycle — blockers, eligibility anomalies, duplicate-rate spikes, and volume shifts — with a complete audit trail surfaced in `docs/Encounters_QA_Report.html` and `docs/UAT_Evidence_Pack.html`.
- **Result:** 219 total rejects triaged over the story window; every BLOCKER and HIGH defect resolved before submission; no uncontrolled anomaly flags remain open at close.

---

## Problem & Operating Setting

HarborPoint Health Plan is a mid-size managed care organization that contracts with delegated vendors to receive encounter data for two lines of business: Medicaid and Commercial. Each week, those vendors deliver encounter batches — adjudicated claim records representing healthcare services rendered — which the Encounters team must validate and submit to external reporting endpoints (state Medicaid agencies, federal programs).

The challenge is that no encounter batch arrives clean. Records can fail for reasons ranging from a missing diagnosis code to a member whose eligibility window does not cover the service date. When a batch carries a blocking defect and is submitted anyway, the agency rejects it wholesale, the plan loses the submission window, and the ops team must scramble on an out-of-cycle resubmission. The business needs a repeatable, documented process that catches these problems internally before any data leaves the building.

The unit of work is the weekly batch, segmented by LOB and vendor. The team's job each week is to run QA, triage what they find, make a fast go/no-go decision, and route defects to the right owner for remediation. This project simulates that workflow in full, using synthetic PHI-free data, and packages every artifact a hiring manager or auditor would need to evaluate the process.

---

## What I Built

| Artifact | Purpose |
|---|---|
| `docs/Encounters_QA_Report.html` | Executive-facing HTML report: charts, triage table, 10-week story |
| `docs/UAT_Evidence_Pack.html` | UAT evidence for 17 test scenarios with pass/fail results |
| `docs/runbook_v0_1.md` | Step-by-step operating SOP: prepare → validate → submit → remediate |
| `docs/kpi_snapshot.md` | Point-in-time KPI snapshot derived from live outputs |
| `outputs/rejects.csv` | Row-level reject detail: code, severity, batch, week |
| `outputs/triage_summary.csv` | Weekly aggregated triage by severity and reject code |
| `outputs/submission_tracker_template.csv` | Ops tracker: status, owner, SLA date, rerun/resubmit notes |
| `src/generate_dataset.py` | Seeded synthetic dataset generator |
| `src/verify_dataset.py` | Post-generation integrity checks |

---

## How the System Works

Validation runs against two input files — encounter headers and encounter line items — cross-referenced against reference member and provider rosters. The output is `outputs/rejects.csv`, where every row that fails a quality rule is recorded with its reject code, severity, batch identifier, and week.

**Severity tiers:**
- **BLOCKER** — defects that must be remediated before submission (e.g., `NULL_DX`, `NULL_PROC`, missing required fields). A single BLOCKER in a batch gates the entire submission.
- **HIGH** — elevated-risk defects that require remediation and reprocessing before submit (e.g., `MEMBER_ELIGIBILITY` failures).
- **MONITOR** — defects where submission can proceed with controls and weekly trend tracking (e.g., financial ratio flags, code-set anomalies).

On top of row-level rules, three **batch anomaly flags** fire when aggregate behavior crosses a threshold:

| Rule | Trigger | Action |
|---|---|---|
| R901 `DUP_RATE_GT_1PCT` | Duplicate claim key rate > 1 % | HIGH — remediate and reprocess |
| R902 `ELIG_MISMATCH_GT_2PCT` | Eligibility mismatch rate > 2 % | HIGH — remediate and reprocess |
| R903 `VOLUME_SHIFT_GT_15PCT` | Batch volume shift > 15 % vs. prior week | MONITOR — submit with controls |

The distinction matters operationally: a row-level BLOCKER means a specific record is broken; a batch anomaly flag means the overall batch exhibits a pattern that warrants investigation even if individual rows are individually valid.

---

## The 10-Week Story

The synthetic story window runs from late February through late April 2026 and is designed to exercise every decision the ops team can face.

**W02 (2026-03-02) — Blockers.** The first significant week surfaced 70 BLOCKER rejects driven by required-field gaps (30), provider data problems (30), and date logic failures (10). Decision: Hold. The batch did not submit.

**W06 (2026-03-30) — Eligibility + R902.** After three clean weeks, seven HIGH rejects appeared in the member eligibility category (`R010` code × 6) alongside a single R902 batch-level anomaly flag, indicating the eligibility mismatch rate had crossed 2 %. Decision: Remediate and reprocess before submit.

**W07 (2026-04-06) — Duplicates + R901 + Monitors.** The heaviest week: 11 HIGH defects (10 `DUP_CLAIM_KEY` records plus R901 anomaly flag) and 120 MONITOR-severity signals (80 financial ratio flags, 40 code-set warnings). Decision: Remediate duplicates; submit only after duplicate clean-up; monitor financial and code-set noise on trend.

**W10 (2026-04-27) — Volume + R903 only.** The story closes with a single MONITOR-severity entry: the R903 volume-shift anomaly, indicating batch volume moved more than 15 % week-over-week. No BLOCKERs, no HIGH defects. Decision: Submit with volume monitor controls in place.

This arc — blockers, then eligibility risk, then duplicates with monitors, then a clean volume signal — exercises the full incident taxonomy and is traceable through every output artifact.

---

## Results & KPIs

All figures are sourced from `docs/kpi_snapshot.md`.

- **Total rejects (story window):** 219
- **By severity:** BLOCKER 80 · HIGH 18 · MONITOR 121
- **Top 5 reject codes:** `ALLOWED_GT_CHARGE` (40), `PAID_GT_ALLOWED` (40), `NULL_DX` (20), `NULL_PROC` (20), `DUP_CLAIM_KEY` (10)
- **Batch anomaly flags triggered:** R901 (week of 2026-04-06), R902 (week of 2026-03-30), R903 (week of 2026-04-27)
- All three anomaly flags were handled per the decision table in `docs/runbook_v0_1.md`; no flag remained unresolved at story close.

---

## How You'd Use This in Ops

The workflow follows the canonical loop documented in `docs/runbook_v0_1.md`:

1. **Prepare** — confirm vendor files and reference data are current for the run period.
2. **Validate** — run `src/generate_dataset.py` + `src/verify_dataset.py` to produce `outputs/rejects.csv` and `outputs/triage_summary.csv`.
3. **Review** — open `docs/Encounters_QA_Report.html`; prioritize BLOCKERs, then HIGH, then MONITOR trends.
4. **Submit** — if no BLOCKERs and no open HIGH anomalies, proceed to agency handoff; update `outputs/submission_tracker_template.csv`.
5. **Intake** — capture agency acknowledgment or rejection response; record in tracker.
6. **Reprocess** — assign remediation to vendor or internal IT; execute targeted fix and regenerate batch.
7. **Resubmit** — rerun validation to confirm gates pass; resubmit; close the cycle with an RCA-lite note.

The tracker (`outputs/submission_tracker_template.csv`) is the single source of operational truth for ownership, SLA dates, and rerun history.

---

## Limits / Out of Scope

- **Not provider billing QA.** This system validates encounter records submitted by a health plan to regulatory reporting endpoints. It does not adjudicate claims, evaluate provider billing accuracy, or support revenue cycle management.
- **Not an EDI/837 parser.** All processing is tabular (CSV). The system does not parse X12 EDI transaction sets, does not handle HIPAA 837 transaction validation, and does not interface with EDI clearinghouses.
- **Synthetic data only.** All member, provider, and encounter data are fully synthetic and PHI-free. Production deployment would require integration with live feed pipelines and reference data stores.

---

## Next Steps

- **Automate the weekly run** via a scheduled task or CI job that triggers dataset generation, validation, and report export on each Monday morning batch delivery.
- **Extend anomaly rules** to include financial-ratio thresholds (e.g., `ALLOWED_GT_CHARGE` rate > 5 %) as HIGH-severity batch flags rather than MONITOR-only signals.
- **Add a remediation SLA dashboard** built on `outputs/submission_tracker_template.csv` to surface overdue reprocessing assignments in the `docs/Encounters_QA_Report.html` view.
