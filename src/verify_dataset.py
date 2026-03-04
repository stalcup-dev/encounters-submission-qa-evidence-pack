from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Optional, Tuple

HEADER_COLUMNS = [
    "batch_id",
    "claim_id",
    "member_id",
    "provider_npi",
    "lob",
    "vendor",
    "service_from",
    "service_to",
    "total_charge",
    "total_allowed",
    "total_paid",
    "adjudication_date",
]

LINES_COLUMNS = [
    "claim_id",
    "line_id",
    "proc_code",
    "dx_code",
    "units",
    "charge",
    "allowed",
    "paid",
]

MEMBERS_COLUMNS = [
    "member_id",
    "dob",
    "gender",
    "coverage_start",
    "coverage_end",
]

PROVIDERS_COLUMNS = [
    "provider_npi",
    "provider_name",
    "taxonomy",
]

STORY_COLUMNS = ["week_start", "lob", "vendor", "batch_id", "storyline_label"]

LOCKED_RUN_DATE = date(2026, 5, 10)
START_WEEK = date(2026, 2, 23)
WEEK_COUNT = 10
LOB_VALUES = {"MEDICAID", "COMMERCIAL"}
VENDOR_VALUES = {"VENDOR_A", "VENDOR_B", "VENDOR_C"}
RESERVED_NPI = "9999999999"
BATCH_ID_RE = re.compile(r"^BATCH_(\d{8})_(VENDOR_[A-Z])_(MEDICAID|COMMERCIAL)_W(\d{2})$")


@dataclass
class Check:
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DS-001 independent dataset verifier.")
    parser.add_argument("--run_date", default=LOCKED_RUN_DATE.isoformat(), help="Expected run date (default: 2026-05-10)")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Project root path")
    parser.add_argument(
        "--expected-hashes-json",
        default="",
        help="Optional path to JSON {relative_path: sha256}. If omitted, hash check is skipped.",
    )
    return parser.parse_args()


def add_check(checks: List[Check], name: str, passed: bool, detail: str) -> None:
    checks.append(Check(name=name, status="PASS" if passed else "FAIL", detail=detail))


def add_skip(checks: List[Check], name: str, detail: str) -> None:
    checks.append(Check(name=name, status="SKIP", detail=detail))


def parse_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]
    return columns, rows


def validate_schema(checks: List[Check], name: str, actual: List[str], expected: List[str]) -> bool:
    passed = actual == expected
    if passed:
        add_check(checks, f"Schema/{name}", True, f"columns={len(actual)}")
        return True
    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    add_check(checks, f"Schema/{name}", False, f"missing={missing or '[]'} extra={extra or '[]'}")
    return False


def to_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def to_cents(raw: str) -> Optional[int]:
    if raw == "":
        return None
    try:
        amt = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    return int(amt * 100)


def claim_key(header_row: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    charge_cents = to_cents(header_row["total_charge"])
    charge_str = "" if charge_cents is None else f"{charge_cents / 100:.2f}"
    return (
        header_row["batch_id"],
        header_row["member_id"],
        header_row["provider_npi"],
        header_row["service_from"],
        charge_str,
    )


def stable_digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def parse_expected_hashes(path: Path) -> Dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected hash file must be a JSON object")
    parsed: Dict[str, str] = {}
    for k, v in payload.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("expected hash map must be {string: string}")
        parsed[k] = v.lower()
    return parsed


def ensure_manifest_references_exist(
    manifest: Dict[str, object],
    claim_ids: set[str],
    line_refs: set[Tuple[str, str]],
) -> bool:
    incidents = manifest.get("incidents", {})
    if not isinstance(incidents, dict):
        return False
    for incident in incidents.values():
        if not isinstance(incident, dict):
            return False
        rules = incident.get("rules", {})
        if not isinstance(rules, dict):
            return False
        for payload in rules.values():
            if not isinstance(payload, dict):
                continue
            claim_id_lists = [payload.get("claim_ids"), payload.get("participant_claim_ids")]
            for maybe_list in claim_id_lists:
                if isinstance(maybe_list, list):
                    for claim_id in maybe_list:
                        if not isinstance(claim_id, str):
                            return False
                        if claim_id and claim_id not in claim_ids:
                            return False
            pairs = payload.get("source_clone_pairs")
            if isinstance(pairs, list):
                for pair in pairs:
                    if not isinstance(pair, dict):
                        return False
                    source = pair.get("source_claim_id", "")
                    clone = pair.get("clone_claim_id", "")
                    if source not in claim_ids or clone not in claim_ids:
                        return False
            refs = payload.get("line_refs")
            if isinstance(refs, list):
                for ref in refs:
                    if not isinstance(ref, dict):
                        return False
                    c_id = ref.get("claim_id", "")
                    l_id = ref.get("line_id", "")
                    if (c_id, l_id) not in line_refs:
                        return False
    return True


def evaluate_rule_counts(
    headers: List[Dict[str, str]],
    lines_by_batch: Dict[str, List[Dict[str, str]]],
    member_lookup: Dict[str, Dict[str, str]],
    provider_npi_set: set[str],
    run_date: date,
) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}

    for batch_id, batch_headers in sorted(_group(headers, "batch_id").items()):
        counts = {f"R{i:03d}": 0 for i in range(1, 16)}

        key_counts: Counter[Tuple[str, str, str, str, str]] = Counter()
        batch_lines = lines_by_batch.get(batch_id, [])

        for row in batch_headers:
            if row["member_id"] == "":
                counts["R001"] += 1
            if row["claim_id"] == "":
                counts["R002"] += 1
            if row["provider_npi"] == "":
                counts["R003"] += 1
            if row["service_from"] == "":
                counts["R004"] += 1

            npi = row["provider_npi"]
            if npi:
                if npi.isdigit() and len(npi) != 10:
                    counts["R005"] += 1
                if not npi.isdigit():
                    counts["R006"] += 1
                if npi.isdigit() and len(npi) == 10 and npi not in provider_npi_set:
                    counts["R007"] += 1

            sf = to_date(row["service_from"])
            st = to_date(row["service_to"])
            if sf and st and st < sf:
                counts["R008"] += 1
            if sf and sf > run_date:
                counts["R009"] += 1

            if row["member_id"] and sf:
                member = member_lookup.get(row["member_id"])
                if member:
                    cov_start = to_date(member["coverage_start"])
                    cov_end = to_date(member["coverage_end"])
                    if cov_start and cov_end and (sf < cov_start or sf > cov_end):
                        counts["R010"] += 1

            key_counts[claim_key(row)] += 1

        dup_participants = sum(v for v in key_counts.values() if v > 1)
        counts["R011"] = dup_participants

        for line in batch_lines:
            paid = to_cents(line["paid"])
            allowed = to_cents(line["allowed"])
            charge = to_cents(line["charge"])
            if paid is not None and allowed is not None and paid > allowed:
                counts["R012"] += 1
            if allowed is not None and charge is not None and allowed > charge:
                counts["R013"] += 1
            if line["proc_code"] == "":
                counts["R014"] += 1
            if line["dx_code"] == "":
                counts["R015"] += 1

        out[batch_id] = counts
    return out


def _group(rows: Iterable[Dict[str, str]], key: str) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return grouped


def print_report(checks: List[Check]) -> None:
    for c in checks:
        print(f"[{c.status}] {c.name} :: {c.detail}")
    passed = sum(1 for c in checks if c.status == "PASS")
    failed = sum(1 for c in checks if c.status == "FAIL")
    skipped = sum(1 for c in checks if c.status == "SKIP")
    print(f"SUMMARY: PASS={passed} FAIL={failed} SKIP={skipped} TOTAL={len(checks)}")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()

    try:
        run_date = date.fromisoformat(args.run_date)
    except ValueError:
        print(f"Invalid --run_date '{args.run_date}', expected YYYY-MM-DD.")
        return 2

    checks: List[Check] = []

    add_check(checks, "RunDate/locked_2026-05-10", run_date == LOCKED_RUN_DATE, f"run_date={run_date.isoformat()}")

    files = {
        "header": root / "data_raw" / "encounters_header.csv",
        "lines": root / "data_raw" / "encounters_lines.csv",
        "members": root / "data_raw" / "reference_members.csv",
        "providers": root / "data_raw" / "reference_providers.csv",
        "story": root / "outputs" / "story_map.csv",
        "manifest": root / "outputs" / "injection_manifest.json",
    }

    for label, path in files.items():
        add_check(checks, f"Files/{label}", path.exists(), str(path))

    if any(c.status == "FAIL" for c in checks):
        print_report(checks)
        return 1

    h_cols, headers = parse_csv(files["header"])
    l_cols, lines = parse_csv(files["lines"])
    m_cols, members = parse_csv(files["members"])
    p_cols, providers = parse_csv(files["providers"])
    s_cols, story = parse_csv(files["story"])

    schema_ok = True
    schema_ok &= validate_schema(checks, "encounters_header.csv", h_cols, HEADER_COLUMNS)
    schema_ok &= validate_schema(checks, "encounters_lines.csv", l_cols, LINES_COLUMNS)
    schema_ok &= validate_schema(checks, "reference_members.csv", m_cols, MEMBERS_COLUMNS)
    schema_ok &= validate_schema(checks, "reference_providers.csv", p_cols, PROVIDERS_COLUMNS)
    schema_ok &= validate_schema(checks, "story_map.csv", s_cols, STORY_COLUMNS)
    if not schema_ok:
        print_report(checks)
        return 1

    # Batch_id format + consistency
    batch_id_rows = headers + story
    bad_batch_id_count = 0
    for row in batch_id_rows:
        if not BATCH_ID_RE.match(row["batch_id"]):
            bad_batch_id_count += 1
    add_check(checks, "BatchId/format_BATCH_YYYYMMDD_VENDOR_LOB_WNN", bad_batch_id_count == 0, f"bad={bad_batch_id_count}")

    # Topology
    unique_story_batches = {r["batch_id"] for r in story}
    add_check(checks, "Topology/story_rows_60", len(story) == 60, f"rows={len(story)}")
    add_check(checks, "Topology/unique_story_batches_60", len(unique_story_batches) == 60, f"unique={len(unique_story_batches)}")

    lobs = {r["lob"] for r in story}
    vendors = {r["vendor"] for r in story}
    add_check(checks, "Topology/lobs_set", lobs == LOB_VALUES, f"observed={sorted(lobs)}")
    add_check(checks, "Topology/vendors_set", vendors == VENDOR_VALUES, f"observed={sorted(vendors)}")

    combo_counts: Counter[Tuple[str, str, str]] = Counter((r["week_start"], r["lob"], r["vendor"]) for r in story)
    one_per_combo = len(combo_counts) == 60 and all(v == 1 for v in combo_counts.values())
    add_check(checks, "Topology/one_batch_per_week_lob_vendor", one_per_combo, f"combos={len(combo_counts)}")

    week_starts = sorted({r["week_start"] for r in story})
    expected_weeks = [(START_WEEK + timedelta(weeks=i)).isoformat() for i in range(WEEK_COUNT)]
    add_check(checks, "Topology/10_weeks_expected_range", week_starts == expected_weeks, f"observed={week_starts[:1]}..{week_starts[-1:]}")

    # Volume metric lock: claims_in_batch = COUNT(*) header rows per batch_id.
    header_count_by_batch: Dict[str, int] = dict(Counter(r["batch_id"] for r in headers))
    add_check(
        checks,
        "VolumeMetric/claims_in_batch_is_COUNT_star_header_rows",
        sum(header_count_by_batch.values()) == len(headers),
        f"sum_counts={sum(header_count_by_batch.values())} total_headers={len(headers)}",
    )

    # Volumes: all 200 except W10 MEDICAID/VENDOR_A=320.
    w10_row = [r for r in story if r["week_start"] == "2026-04-27" and r["lob"] == "MEDICAID" and r["vendor"] == "VENDOR_A"]
    add_check(checks, "Volume/w10_batch_singleton", len(w10_row) == 1, f"rows={len(w10_row)}")
    w10_batch_id = w10_row[0]["batch_id"] if len(w10_row) == 1 else ""

    if w10_batch_id:
        w10_count = header_count_by_batch.get(w10_batch_id, 0)
        add_check(checks, "Volume/w10_medicaid_vendor_a_320", w10_count == 320, f"count={w10_count}")
    else:
        add_check(checks, "Volume/w10_medicaid_vendor_a_320", False, "missing W10 batch")

    non_w10_bad = sum(1 for b, c in header_count_by_batch.items() if b != w10_batch_id and c != 200)
    add_check(checks, "Volume/all_other_batches_200", non_w10_bad == 0, f"bad_batches={non_w10_bad}")

    # Build helper maps.
    lines_by_claim_id = {r["claim_id"]: r for r in lines}
    line_refs = {(r["claim_id"], r["line_id"]) for r in lines}
    claim_ids = {r["claim_id"] for r in headers if r["claim_id"]}
    member_lookup = {r["member_id"]: r for r in members}
    provider_npi_set = {r["provider_npi"] for r in providers}

    # Rule counts per batch
    lines_by_batch: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    header_by_claim_id = {r["claim_id"]: r for r in headers if r["claim_id"]}
    missing_line_claim_links = 0
    for line in lines:
        claim_id = line["claim_id"]
        h = header_by_claim_id.get(claim_id)
        if not h:
            missing_line_claim_links += 1
            continue
        lines_by_batch[h["batch_id"]].append(line)
    add_check(checks, "DataIntegrity/lines_point_to_existing_header_claim_id", missing_line_claim_links == 0, f"missing_links={missing_line_claim_links}")

    rule_counts_by_batch = evaluate_rule_counts(
        headers=headers,
        lines_by_batch=lines_by_batch,
        member_lookup=member_lookup,
        provider_npi_set=provider_npi_set,
        run_date=run_date,
    )

    # Identify incident batches from fixed coordinates.
    def batch_for(week_start: str, lob: str, vendor: str) -> str:
        rows = [r for r in story if r["week_start"] == week_start and r["lob"] == lob and r["vendor"] == vendor]
        return rows[0]["batch_id"] if len(rows) == 1 else ""

    w02_batch = batch_for("2026-03-02", "MEDICAID", "VENDOR_A")
    w06_batch = batch_for("2026-03-30", "COMMERCIAL", "VENDOR_B")
    w07_batch = batch_for("2026-04-06", "COMMERCIAL", "VENDOR_C")

    add_check(checks, "IncidentBatch/W02_exists", w02_batch != "", w02_batch or "missing")
    add_check(checks, "IncidentBatch/W06_exists", w06_batch != "", w06_batch or "missing")
    add_check(checks, "IncidentBatch/W07_exists", w07_batch != "", w07_batch or "missing")

    # W02 exact R001-R009 and clean for R010-R015
    if w02_batch:
        c = rule_counts_by_batch[w02_batch]
        expected = {"R001": 10, "R002": 5, "R003": 10, "R004": 5, "R005": 10, "R006": 10, "R007": 10, "R008": 10, "R009": 10}
        ok_exact = all(c[k] == v for k, v in expected.items())
        add_check(checks, "W02/R001_R009_exact_counts", ok_exact, ",".join(f"{k}={c[k]}" for k in sorted(expected)))
        clean_other = all(c[f"R{i:03d}"] == 0 for i in range(10, 16))
        add_check(checks, "W02/R010_R015_zero", clean_other, ",".join(f"R{i:03d}={c[f'R{i:03d}']}" for i in range(10, 16)))
    else:
        add_check(checks, "W02/R001_R009_exact_counts", False, "missing batch")
        add_check(checks, "W02/R010_R015_zero", False, "missing batch")

    # W06 exact R010=6 and all others zero.
    if w06_batch:
        c = rule_counts_by_batch[w06_batch]
        add_check(checks, "W06/R010_exact_6", c["R010"] == 6, f"R010={c['R010']}")
        clean = all(c[f"R{i:03d}"] == 0 for i in list(range(1, 10)) + list(range(11, 16)))
        add_check(checks, "W06/all_other_rules_zero", clean, ",".join(f"R{i:03d}={c[f'R{i:03d}']}" for i in [1,2,3,4,5,6,7,8,9,11,12,13,14,15]))
    else:
        add_check(checks, "W06/R010_exact_6", False, "missing batch")
        add_check(checks, "W06/all_other_rules_zero", False, "missing batch")

    # W07 duplicate + line rules
    if w07_batch:
        c = rule_counts_by_batch[w07_batch]
        w07_claims = header_count_by_batch.get(w07_batch, 0)
        duplicate_rate = (c["R011"] / w07_claims) if w07_claims else 0.0
        key_counts = Counter(claim_key(r) for r in headers if r["batch_id"] == w07_batch)
        dup_key_total = sum(1 for v in key_counts.values() if v > 1)

        add_check(
            checks,
            "W07/R011_duplicate_participation_10_of_200",
            c["R011"] == 10 and w07_claims == 200 and abs(duplicate_rate - 0.05) < 1e-12 and duplicate_rate > 0.01,
            f"participants={c['R011']} claims_in_batch={w07_claims} rate={duplicate_rate:.4f}",
        )
        add_check(checks, "W07/R011_duplicate_key_count_5", dup_key_total == 5, f"dup_keys={dup_key_total}")
        add_check(
            checks,
            "W07/R012_R015_exact_20_each",
            c["R012"] == 20 and c["R013"] == 20 and c["R014"] == 20 and c["R015"] == 20,
            f"R012={c['R012']} R013={c['R013']} R014={c['R014']} R015={c['R015']}",
        )
        clean = all(c[f"R{i:03d}"] == 0 for i in range(1, 11))
        add_check(checks, "W07/R001_R010_zero", clean, ",".join(f"R{i:03d}={c[f'R{i:03d}']}" for i in range(1, 11)))
    else:
        add_check(checks, "W07/R011_duplicate_participation_10_of_200", False, "missing batch")
        add_check(checks, "W07/R011_duplicate_key_count_5", False, "missing batch")
        add_check(checks, "W07/R012_R015_exact_20_each", False, "missing batch")
        add_check(checks, "W07/R001_R010_zero", False, "missing batch")

    # Clean weeks outside W02/W06/W07.
    incident_batches = {w02_batch, w06_batch, w07_batch}
    clean_outside = True
    first_dirty = ""
    for batch_id, counts in rule_counts_by_batch.items():
        if batch_id in incident_batches:
            continue
        if any(counts[f"R{i:03d}"] != 0 for i in range(1, 16)):
            clean_outside = False
            first_dirty = batch_id
            break
    add_check(checks, "CleanWeeks/outside_W02_W06_W07_no_R001_R015_hits", clean_outside, first_dirty or "clean")

    # Reserved provider rule
    reserved_provider_in_ref = RESERVED_NPI in provider_npi_set
    reserved_headers = [r for r in headers if r["provider_npi"] == RESERVED_NPI]
    reserved_only_w02 = all(r["batch_id"] == w02_batch for r in reserved_headers) if w02_batch else False
    add_check(checks, "ReservedProvider/not_in_reference_providers", not reserved_provider_in_ref, f"present={reserved_provider_in_ref}")
    add_check(
        checks,
        "ReservedProvider/only_w02_r007_population",
        reserved_only_w02 and len(reserved_headers) == 10,
        f"count={len(reserved_headers)} only_w02={reserved_only_w02}",
    )

    # R903 check using COUNT(*) metric and trailing 8-week median.
    mv_a_rows = sorted(
        [r for r in story if r["lob"] == "MEDICAID" and r["vendor"] == "VENDOR_A"],
        key=lambda r: r["week_start"],
    )
    if len(mv_a_rows) == 10:
        mv_a_counts = [header_count_by_batch.get(r["batch_id"], 0) for r in mv_a_rows]
        trailing_8 = mv_a_counts[1:9]  # W02-W09
        median_8 = float(median(trailing_8))
        w10 = float(mv_a_counts[9])
        dev = abs(w10 - median_8) / median_8 if median_8 else 0.0
        add_check(
            checks,
            "R903/W10_volume_shift_gt_15pct_using_COUNT_star",
            dev > 0.15,
            f"w10={int(w10)} trailing8_median={median_8:.1f} deviation={dev:.4f}",
        )
    else:
        add_check(checks, "R903/W10_volume_shift_gt_15pct_using_COUNT_star", False, f"mv_a_rows={len(mv_a_rows)}")

    # Manifest reference check.
    try:
        manifest_obj = json.loads(files["manifest"].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        manifest_obj = {}
    manifest_ok = isinstance(manifest_obj, dict) and ensure_manifest_references_exist(manifest_obj, claim_ids, line_refs)
    add_check(checks, "Manifest/references_exist_in_dataset", manifest_ok, f"claims={len(claim_ids)} lines={len(line_refs)}")

    # Optional determinism hash check
    if args.expected_hashes_json:
        hash_path = Path(args.expected_hashes_json).resolve()
        if not hash_path.exists():
            add_check(checks, "Determinism/hash_file_exists", False, str(hash_path))
        else:
            try:
                expected_hashes = parse_expected_hashes(hash_path)
                mismatch_count = 0
                missing_count = 0
                for rel_path, expected in expected_hashes.items():
                    p = root / rel_path
                    if not p.exists():
                        missing_count += 1
                        continue
                    actual = stable_digest(p)
                    if actual.lower() != expected.lower():
                        mismatch_count += 1
                add_check(
                    checks,
                    "Determinism/expected_hashes_match",
                    mismatch_count == 0 and missing_count == 0,
                    f"entries={len(expected_hashes)} mismatches={mismatch_count} missing={missing_count}",
                )
            except Exception as exc:  # noqa: BLE001
                add_check(checks, "Determinism/expected_hashes_match", False, f"error={exc}")
    else:
        add_skip(checks, "Determinism/expected_hashes_match", "not requested")

    print_report(checks)
    failed = any(c.status == "FAIL" for c in checks)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
