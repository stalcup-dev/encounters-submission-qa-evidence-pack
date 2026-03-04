# Start Here (Hiring Manager)

## What this project is
This is an **Encounters submission QA evidence pack**.
It shows how encounter batches are checked before submission, how issues are triaged, how remediation is tracked, and how UAT evidence is captured.

## Scenario (public-safe)
HarborPoint Health Plan receives weekly encounter batches from delegated vendors for multiple lines of business (e.g., Medicaid and Commercial). Before submitting these encounters to external reporting endpoints (state/federal programs), the Encounters team must catch blocking defects, prioritize remediation, and document a defensible audit trail.

This evidence pack simulates that workflow end-to-end:
- Row-level rejects (missing member/provider fields, invalid dates, eligibility outside coverage, duplicates, etc.)
- Batch-level flags when operational thresholds are exceeded (duplicate rate >1%, eligibility mismatch >2%, volume shift >15%)
- Ops decisions: Hold / Reprocess / Submit-with-monitoring
- UAT traceability for upgrades and vendor feed changes

Out of scope: This is not provider billing QA and not an EDI/837 parser; it's tabular pre-submit QA for payer encounter reporting.

## Open this first
1. [docs/Encounters_QA_Report.html](Encounters_QA_Report.html)

This report is the fastest way to understand the story, the issues found, and the operational decisions.

## Quick Start (Repro)
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

## 10-week story (in 4 bullets)
- **W02 (2026-03-02):** Blockers were found in one batch (required fields, provider data, and date logic), so submission was held.
- **W06 (2026-03-30):** Eligibility issues rose and triggered an anomaly flag (`R902`), so remediation/reprocessing was required.
- **W07 (2026-04-06):** Duplicate claims plus monitoring signals triggered a second anomaly flag (`R901`), confirming process risk in that week.
- **W10 (2026-04-27):** Volume shifted sharply and triggered a volume anomaly flag (`R903`), which was handled with monitoring controls.

## What each artifact proves
- [docs/runbook_v0_1.md](runbook_v0_1.md): Proves there is a clear, repeatable operating process for prepare -> validate -> submit -> remediate.
- [docs/UAT_Evidence_Pack.html](UAT_Evidence_Pack.html): Proves rules were tested end-to-end with evidence for each test case.
- [outputs/submission_tracker_template.csv](../outputs/submission_tracker_template.csv): Proves submissions can be tracked with status, owner, due dates, and rerun/resubmit notes.

## Glossary (plain language)
- **Encounters:** Records of healthcare services submitted for reporting and payment operations.
- **Batch:** A group of encounter records processed and submitted together.
- **LOB (Line of Business):** Product segment (for example, Medicaid or Commercial).
- **Vendor:** External or internal partner providing encounter files.
- **Reject:** A record that fails a quality check and cannot pass as-is.
- **Triage:** Prioritizing and organizing issues so teams know what to fix first.
- **Anomaly flag:** A warning that overall batch behavior is unusual (for example, a spike in duplicates or volume).
- **Reprocess/Resubmit:** Correcting data, rerunning the batch, and sending it again.
