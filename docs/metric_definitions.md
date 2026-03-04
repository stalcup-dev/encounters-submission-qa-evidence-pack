# Metric Definitions

## Purpose
Canonical metric definitions for encounter QA reporting artifacts:
- `outputs/rejects.csv`
- `outputs/triage_summary.csv`
- `outputs/submission_tracker_template.csv`

All rates and counts in dashboards, runbooks, and report narratives should use these definitions.

## Schema and Traceability Note
- Final `outputs/rejects.csv` is a **10-column export** and excludes `rule_id` by design.
- `rule_id` exists in intermediate validation outputs for internal traceability and UAT/test joins.
- Final export behavior is intentional: **`COPY TO` intentionally drops `rule_id`** in the final `rejects.csv` projection.

## Core Count Metrics
| metric_name | artifact(s) | definition | numerator | denominator | grain | threshold |
|---|---|---|---|---|---|---|
| `reject_rows` | `rejects.csv` | Total number of reject rows output by validation (row-level + batch-anomaly rows). | Count of rows in `rejects.csv` | N/A | dataset run | None |
| `reject_count` | `triage_summary.csv` | Aggregated reject volume for a grouped bucket. | Count of `rejects.csv` rows mapped to the same `(week_start, lob, vendor, reject_category, severity)` | N/A | `week_start, lob, vendor, reject_category, severity` | None |
| `affected_claims` | `triage_summary.csv` | Number of distinct impacted claims in a grouped bucket. For batch anomalies, claim uses `BATCH::<batch_id>` convention. | Distinct `claim_id` count within grouped bucket | N/A | `week_start, lob, vendor, reject_category, severity` | None |
| `claims_in_batch` | tracker | Total claims in the submitted/reprocessed batch. Use header-row count from encounter headers. | Count of rows in `encounters_header.csv` for `batch_id` | N/A | `batch_id` | None |
| `rejects_total` | tracker | Total rejects tied to batch at checkpoint. | Sum of reject rows for `batch_id` across severities | N/A | `batch_id` | None |
| `blockers` | tracker | Batch reject rows at `severity=BLOCKER`. | Count of reject rows where `severity='BLOCKER'` and `batch_id` matches | N/A | `batch_id` | Operational gate: must be `0` to pass submit gate |
| `high` | tracker | Batch reject rows at `severity=HIGH`. | Count of reject rows where `severity='HIGH'` and `batch_id` matches | N/A | `batch_id` | Operational gate: batch anomaly highs require remediation/reprocessing |
| `monitor` | tracker | Batch reject rows at `severity=MONITOR`. | Count of reject rows where `severity='MONITOR'` and `batch_id` matches | N/A | `batch_id` | Monitor/trend; no automatic hard stop by itself |

## Batch Anomaly Rate Metrics
| metric_name | rule_id / reject_code | definition | numerator | denominator | grain | threshold |
|---|---|---|---|---|---|---|
| `duplicate_rate` | `R901` / `DUP_RATE_GT_1PCT` | Share of claims participating in duplicate claim-key groups within a batch. | Number of claims with claim_key `(batch_id, member_id, provider_npi, service_from, total_charge)` that appears more than once in the same batch | `claims_in_batch` (header row count for batch) | `batch_id` | Flag when `duplicate_rate > 0.01` (strictly greater than 1.0%) |
| `eligibility_mismatch_rate` | `R902` / `ELIG_MISMATCH_GT_2PCT` | Share of claims with service date outside member coverage window. | Number of claims failing coverage-window check in batch | `claims_in_batch` (header row count for batch) | `batch_id` | Flag when `eligibility_mismatch_rate > 0.02` (strictly greater than 2.0%) |
| `volume_shift_rate` | `R903` / `VOLUME_SHIFT_GT_15PCT` | Relative deviation of current-week volume from trailing 8-week median for same `(lob, vendor)`. | `abs(current_week_claims - trailing_8wk_median_claims)` | `trailing_8wk_median_claims` | `week_start, lob, vendor` | Flag when `volume_shift_rate > 0.15` (strictly greater than 15.0%) |

Notes:
- `current_week_claims` and `trailing_8wk_median_claims` use `COUNT(*)` at encounter-header grain.
- `R903` is emitted as a batch anomaly row in `rejects.csv` using batch-row convention (`line_id` blank, `service_from` blank, `claim_id=BATCH::<batch_id>`).

## Severity Rollup Definitions
| metric_name | definition | formula | grain |
|---|---|---|---|
| `blocker_rate_in_batch` | Proportion of batch claims associated with blocker rejects. | `blockers / claims_in_batch` | `batch_id` |
| `high_rate_in_batch` | Proportion of batch claims associated with high-severity rejects. | `high / claims_in_batch` | `batch_id` |
| `monitor_rate_in_batch` | Proportion of batch claims associated with monitor-severity rejects. | `monitor / claims_in_batch` | `batch_id` |

## Operational Gate Mapping
| condition | decision |
|---|---|
| `blockers > 0` | Do not submit; remediate and reprocess before revalidation. |
| `blockers = 0` and `high > 0` from `R901`/`R902` | Remediate and reprocess affected batch before submit/resubmit. |
| `blockers = 0` and no unresolved high anomalies, with monitor-only findings | Submit with controls; trend and document RCA-lite notes. |
