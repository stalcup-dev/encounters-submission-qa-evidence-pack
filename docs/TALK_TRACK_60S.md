# 60-Second Talk Track

This project shows how Encounters QA works before submission.  
In plain terms: encounter batches are checked for quality issues, those issues are triaged by severity, and teams decide whether to hold, fix, or proceed.

The quickest walkthrough is:
1. **Storyboard:** I show a 10-week operating story, with four clear incident weeks (W02, W06, W07, W10).
2. **Decisions:** For each week, I map what happened to an operational decision: hold for blockers, remediate/reprocess for high-risk issues, and monitor where appropriate.
3. **Evidence:** I back each decision with artifacts: the QA report, runbook, UAT pack, per-test evidence folders, and traceability.

Three batch anomaly flags are highlighted:
- **R901:** duplicate rate exceeded threshold.
- **R902:** eligibility mismatch rate exceeded threshold.
- **R903:** weekly volume shift exceeded threshold.

This is tabular encounter QA, not an EDI parser.
