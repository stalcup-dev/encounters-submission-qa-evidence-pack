# Encounters QA Storyboard

## Storyboard (10-week timeline)

| week_start | storyline_label | what broke | decision | next_week_delta | next_week_label |
| --- | --- | --- | --- | --- | --- |
| 2026-02-23 | CLEAN | CLEAN: no triage rejects in this week. | Proceed; maintain routine monitor controls | +80 rejects | W02 BLOCKERS |
| 2026-03-02 | W02 BLOCKERS | BLOCKER=70 from REQUIRED_FIELD (30), PROVIDER (30), DATES (10). | Hold submission (BLOCKER present) | -80 rejects | CLEAN |
| 2026-03-09 | CLEAN | CLEAN: no triage rejects in this week. | Proceed; maintain routine monitor controls | 0 rejects | CLEAN |
| 2026-03-16 | CLEAN | CLEAN: no triage rejects in this week. | Proceed; maintain routine monitor controls | 0 rejects | CLEAN |
| 2026-03-23 | CLEAN | CLEAN: no triage rejects in this week. | Proceed; maintain routine monitor controls | +7 rejects | W06 R902 ELIGIBILITY-MISMATCH ANOMALY (>2%) |
| 2026-03-30 | W06 R902 ELIGIBILITY-MISMATCH ANOMALY (>2%) | HIGH=7 in MEMBER_ELIGIBILITY: R010=6 plus R902 anomaly=1. | Remediate and reprocess before submit | +124 rejects | W07 R901 DUPLICATE-RATE ANOMALY (>1%) + MONITORS |
| 2026-04-06 | W07 R901 DUPLICATE-RATE ANOMALY (>1%) + MONITORS | HIGH=11 and MONITOR=120: DUP_CLAIM_KEY=10 + R901=1, FINANCIAL=80, CODE_SET=40. | Remediate duplicates; monitor financial/code-set noise | -131 rejects | CLEAN |
| 2026-04-13 | CLEAN | CLEAN: no triage rejects in this week. | Proceed; maintain routine monitor controls | 0 rejects | CLEAN |
| 2026-04-20 | CLEAN | CLEAN: no triage rejects in this week. | Proceed; maintain routine monitor controls | +1 rejects | W10 R903 VOLUME-SHIFT ANOMALY (>15%) |
| 2026-04-27 | W10 R903 VOLUME-SHIFT ANOMALY (>15%) | MONITOR=1 from VOLUME_SHIFT_GT_15PCT (R903) only. | Submit with volume monitor controls | End of window | End of window |

## Key Findings

- Total triage reject volume in story window is **219**.
- Stable weeks are **CLEAN** with no reject surprises.
- Incident pattern is explicit: W02 blockers, W06 eligibility + R902, W07 duplicates + R901 + monitors, W10 volume + R903 only.
- Visual evidence exported to `outputs/screenshots/top_rejects.png` and `outputs/screenshots/triage_trend.png`.
