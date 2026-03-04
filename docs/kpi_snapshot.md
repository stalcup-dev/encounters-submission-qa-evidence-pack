# KPI Snapshot

Generated (UTC): `2026-03-03T18:29:24+00:00`

Computed from:
- `outputs/triage_summary.csv`
- `outputs/rejects.csv`

## Core Totals
- Total rejects (sum `reject_count`): **219**

## Totals by Severity
| severity | reject_count |
|---|---:|
| BLOCKER | 80 |
| HIGH | 18 |
| MONITOR | 121 |

## Top 5 Reject Codes
| rank | reject_code | reject_count |
|---:|---|---:|
| 1 | ALLOWED_GT_CHARGE | 40 |
| 2 | PAID_GT_ALLOWED | 40 |
| 3 | NULL_DX | 20 |
| 4 | NULL_PROC | 20 |
| 5 | DUP_CLAIM_KEY | 10 |

## Batch Anomaly Flags Present
| rule_id | reject_code | present | weeks |
|---|---|---|---|
| R901 | DUP_RATE_GT_1PCT | yes | 2026-04-06 |
| R902 | ELIG_MISMATCH_GT_2PCT | yes | 2026-03-30 |
| R903 | VOLUME_SHIFT_GT_15PCT | yes | 2026-04-27 |

