from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

TRIAGE_COLUMNS = [
    "week_start",
    "lob",
    "vendor",
    "reject_category",
    "severity",
    "reject_count",
    "affected_claims",
]

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

SEVERITY_ORDER = ["BLOCKER", "HIGH", "MONITOR"]

ANOMALY_RULE_TO_CODE = {
    "R901": "DUP_RATE_GT_1PCT",
    "R902": "ELIG_MISMATCH_GT_2PCT",
    "R903": "VOLUME_SHIFT_GT_15PCT",
}

BATCH_ID_RE = re.compile(r"^BATCH_(\d{8}|\d{4}-\d{2}-\d{2})_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build docs/kpi_snapshot.md from outputs CSVs.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Project root path")
    parser.add_argument(
        "--out",
        default="docs/kpi_snapshot.md",
        help="Output markdown path (relative to --root if not absolute)",
    )
    return parser.parse_args()


def parse_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]
    return columns, rows


def expect_columns(path: Path, actual: List[str], expected: List[str]) -> None:
    if actual == expected:
        return
    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    raise ValueError(f"{path}: schema mismatch; missing={missing or '[]'} extra={extra or '[]'}")


def to_int(raw: str, field_name: str) -> int:
    try:
        return int(raw.strip())
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid integer for {field_name}: {raw!r}") from exc


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
    match = BATCH_ID_RE.match(batch_id.strip())
    if not match:
        return None
    token = match.group(1)
    if "-" in token:
        return try_iso_date(token)
    if len(token) == 8:
        return try_iso_date(f"{token[0:4]}-{token[4:6]}-{token[6:8]}")
    return None


def derive_week_from_reject_row(row: Dict[str, str]) -> date | None:
    service_from = (row.get("service_from") or "").strip()
    if service_from:
        dt = try_iso_date(service_from)
        return monday_of(dt) if dt is not None else None
    return week_from_batch_id((row.get("batch_id") or "").strip())


def build_markdown(
    *,
    triage_rows: List[Dict[str, str]],
    rejects_rows: List[Dict[str, str]],
    triage_path: Path,
    rejects_path: Path,
) -> str:
    total_rejects = 0
    severity_totals: Counter[str] = Counter()
    for row in triage_rows:
        count = to_int(row["reject_count"], "reject_count")
        total_rejects += count
        severity_totals[row["severity"]] += count

    reject_code_counts: Counter[str] = Counter((row["reject_code"] or "").strip() for row in rejects_rows)
    reject_code_counts.pop("", None)
    top_codes = sorted(reject_code_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    anomaly_weeks: Dict[str, set[str]] = defaultdict(set)
    for row in rejects_rows:
        code = (row.get("reject_code") or "").strip()
        if code not in ANOMALY_RULE_TO_CODE.values():
            continue
        week_dt = derive_week_from_reject_row(row)
        if week_dt is not None:
            anomaly_weeks[code].add(week_dt.isoformat())

    generated_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines: List[str] = []
    lines.append("# KPI Snapshot")
    lines.append("")
    lines.append(f"Generated (UTC): `{generated_ts}`")
    lines.append("")
    lines.append("Computed from:")
    lines.append(f"- `{triage_path.as_posix()}`")
    lines.append(f"- `{rejects_path.as_posix()}`")
    lines.append("")
    lines.append("## Core Totals")
    lines.append(f"- Total rejects (sum `reject_count`): **{total_rejects}**")
    lines.append("")
    lines.append("## Totals by Severity")
    lines.append("| severity | reject_count |")
    lines.append("|---|---:|")
    for sev in SEVERITY_ORDER:
        lines.append(f"| {sev} | {severity_totals.get(sev, 0)} |")
    for sev in sorted(s for s in severity_totals if s not in SEVERITY_ORDER):
        lines.append(f"| {sev} | {severity_totals[sev]} |")
    lines.append("")
    lines.append("## Top 5 Reject Codes")
    lines.append("| rank | reject_code | reject_count |")
    lines.append("|---:|---|---:|")
    for idx, (code, count) in enumerate(top_codes, start=1):
        lines.append(f"| {idx} | {code} | {count} |")
    if not top_codes:
        lines.append("| 1 | (none) | 0 |")
    lines.append("")
    lines.append("## Batch Anomaly Flags Present")
    lines.append("| rule_id | reject_code | present | weeks |")
    lines.append("|---|---|---|---|")
    for rule_id, code in ANOMALY_RULE_TO_CODE.items():
        weeks = sorted(anomaly_weeks.get(code, set()))
        present = "yes" if weeks else "no"
        week_text = ", ".join(weeks) if weeks else "-"
        lines.append(f"| {rule_id} | {code} | {present} | {week_text} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    triage_path = root / "outputs" / "triage_summary.csv"
    rejects_path = root / "outputs" / "rejects.csv"
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path

    if not triage_path.exists():
        raise FileNotFoundError(f"missing file: {triage_path}")
    if not rejects_path.exists():
        raise FileNotFoundError(f"missing file: {rejects_path}")

    triage_columns, triage_rows = parse_csv(triage_path)
    rejects_columns, rejects_rows = parse_csv(rejects_path)
    expect_columns(triage_path, triage_columns, TRIAGE_COLUMNS)
    expect_columns(rejects_path, rejects_columns, REJECTS_COLUMNS)

    markdown = build_markdown(
        triage_rows=triage_rows,
        rejects_rows=rejects_rows,
        triage_path=triage_path.relative_to(root),
        rejects_path=rejects_path.relative_to(root),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown + "\n", encoding="utf-8")
    print(f"Wrote KPI snapshot: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
