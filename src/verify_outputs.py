from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REJECTS_COLUMNS = [
    "claim_id",
    "line_id",
    "batch_id",
    "lob",
    "vendor",
    "service_from",
    "reject_category",
    "reject_code",
    "severity",
    "detected_ts",
]

TRIAGE_COLUMNS = [
    "week_start",
    "lob",
    "vendor",
    "reject_category",
    "severity",
    "reject_count",
    "affected_claims",
]

STORY_COLUMNS = ["week_start", "lob", "vendor", "batch_id", "storyline_label"]

ANOMALY_CODE_TO_DIM = {
    "DUP_RATE_GT_1PCT": ("DUPLICATE", "HIGH"),
    "ELIG_MISMATCH_GT_2PCT": ("MEMBER_ELIGIBILITY", "HIGH"),
    "VOLUME_SHIFT_GT_15PCT": ("VOLUME_ANOMALY", "MONITOR"),
}

BATCH_ID_RE = re.compile(r"^BATCH_(\d{8}|\d{4}-\d{2}-\d{2})_")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def parse_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]
    return fieldnames, rows


def add_check(checks: list[Check], name: str, passed: bool, detail: str) -> None:
    checks.append(Check(name=name, passed=passed, detail=detail))


def validate_schema(
    checks: list[Check], dataset: str, actual_columns: list[str] | None, expected_columns: list[str]
) -> bool:
    if actual_columns is None:
        add_check(checks, f"Schema/{dataset}", False, "file not loaded")
        return False
    passed = actual_columns == expected_columns
    if passed:
        add_check(checks, f"Schema/{dataset}", True, f"{len(actual_columns)} columns")
        return True
    missing = [c for c in expected_columns if c not in actual_columns]
    extra = [c for c in actual_columns if c not in expected_columns]
    add_check(
        checks,
        f"Schema/{dataset}",
        False,
        f"missing={missing or '[]'} extra={extra or '[]'}",
    )
    return False


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def try_iso_date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def week_from_batch_id(batch_id: str) -> date | None:
    match = BATCH_ID_RE.match((batch_id or "").strip())
    if not match:
        return None
    token = match.group(1)
    if "-" in token:
        return try_iso_date(token)
    if len(token) == 8:
        return try_iso_date(f"{token[0:4]}-{token[4:6]}-{token[6:8]}")
    return None


def derive_reject_week_start(row: dict[str, str]) -> date | None:
    # Contract lock: derive week_start by parsing YYYYMMDD from batch_id for all rows.
    return week_from_batch_id((row.get("batch_id") or "").strip())


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rejects_path = root / "outputs" / "rejects.csv"
    triage_path = root / "outputs" / "triage_summary.csv"
    story_path = root / "outputs" / "story_map.csv"

    checks: list[Check] = []

    add_check(checks, "Files/rejects.csv", rejects_path.exists(), str(rejects_path))
    add_check(checks, "Files/triage_summary.csv", triage_path.exists(), str(triage_path))
    add_check(checks, "Files/story_map.csv", story_path.exists(), str(story_path))

    rejects_columns: list[str] | None = None
    triage_columns: list[str] | None = None
    story_columns: list[str] | None = None
    rejects_rows: list[dict[str, str]] | None = None
    triage_rows: list[dict[str, str]] | None = None
    story_rows: list[dict[str, str]] | None = None

    if rejects_path.exists():
        rejects_columns, rejects_rows = parse_csv(rejects_path)
    if triage_path.exists():
        triage_columns, triage_rows = parse_csv(triage_path)
    if story_path.exists():
        story_columns, story_rows = parse_csv(story_path)

    rejects_schema_ok = validate_schema(checks, "rejects.csv", rejects_columns, REJECTS_COLUMNS)
    triage_schema_ok = validate_schema(checks, "triage_summary.csv", triage_columns, TRIAGE_COLUMNS)
    story_schema_ok = validate_schema(checks, "story_map.csv", story_columns, STORY_COLUMNS)

    if rejects_schema_ok and triage_schema_ok and story_schema_ok:
        assert rejects_rows is not None
        assert triage_rows is not None
        assert story_rows is not None

        null_week_count = sum(1 for row in triage_rows if (row["week_start"] or "").strip() == "")
        add_check(
            checks,
            "Triage/week_start_non_null",
            null_week_count == 0,
            f"null_rows={null_week_count}",
        )

        story_week_values = sorted({(row.get("week_start") or "").strip() for row in story_rows if (row.get("week_start") or "").strip()})
        triage_week_values = sorted({(row.get("week_start") or "").strip() for row in triage_rows if (row.get("week_start") or "").strip()})
        valid_story_weeks = set(story_week_values)
        out_of_horizon = sorted(w for w in triage_week_values if w not in valid_story_weeks)
        add_check(
            checks,
            "Triage/week_start_within_story_horizon",
            len(out_of_horizon) == 0,
            f"out_of_horizon={out_of_horizon or '[]'}",
        )

        anomaly_reject_counts: dict[str, int] = {}
        for code in ANOMALY_CODE_TO_DIM:
            anomaly_reject_counts[code] = sum(1 for row in rejects_rows if row["reject_code"] == code)
            add_check(
                checks,
                f"AnomalyInRejects/{code}",
                anomaly_reject_counts[code] > 0,
                f"count={anomaly_reject_counts[code]}",
            )

        triage_counts_by_dim: dict[tuple[str, str, str, str, str], int] = {}
        for row in triage_rows:
            key = (
                row["week_start"],
                row["lob"],
                row["vendor"],
                row["reject_category"],
                row["severity"],
            )
            try:
                count = int((row["reject_count"] or "0").strip())
            except ValueError:
                count = -1
            triage_counts_by_dim[key] = count

        expected_anomaly_dims: dict[str, dict[tuple[str, str, str, str, str], int]] = {
            code: {} for code in ANOMALY_CODE_TO_DIM
        }
        bad_week_derivations = 0

        for row in rejects_rows:
            code = row["reject_code"]
            if code not in ANOMALY_CODE_TO_DIM:
                continue
            week_dt = derive_reject_week_start(row)
            if week_dt is None:
                bad_week_derivations += 1
                continue
            category, severity = ANOMALY_CODE_TO_DIM[code]
            key = (
                week_dt.isoformat(),
                row["lob"],
                row["vendor"],
                category,
                severity,
            )
            expected_anomaly_dims[code][key] = expected_anomaly_dims[code].get(key, 0) + 1

        add_check(
            checks,
            "AnomalyAggregation/rejects_week_derivation",
            bad_week_derivations == 0,
            f"failed_rows={bad_week_derivations}",
        )

        for code, expected_keys in expected_anomaly_dims.items():
            matched = 0
            undersized = 0
            for key, expected_count in expected_keys.items():
                triage_count = triage_counts_by_dim.get(key)
                if triage_count is None:
                    continue
                if triage_count >= expected_count:
                    matched += 1
                else:
                    undersized += 1
            add_check(
                checks,
                f"AnomalyInTriage/{code}",
                len(expected_keys) > 0 and matched == len(expected_keys) and undersized == 0,
                f"expected_keys={len(expected_keys)} matched={matched} undersized={undersized}",
            )

    total = len(checks)
    passed = sum(1 for c in checks if c.passed)
    failed = total - passed

    print("GCT-061 Output Verifier")
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"[{status}] {c.name} :: {c.detail}")
    print(f"SUMMARY: {passed}/{total} checks passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
