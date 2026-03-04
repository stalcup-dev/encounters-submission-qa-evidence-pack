from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

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

LOB_VALUES = ["MEDICAID", "COMMERCIAL"]
VENDOR_VALUES = ["VENDOR_A", "VENDOR_B", "VENDOR_C"]
RESERVED_NPI_NOT_FOUND = "9999999999"


@dataclass(frozen=True)
class BatchPlan:
    week_label: str
    week_start: date
    lob: str
    vendor: str
    batch_id: str
    claim_target: int
    storyline_label: str


class MemberFactory:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.counter = 0
        self.member_rows: List[Dict[str, str]] = []
        self.member_index: Dict[str, Dict[str, str]] = {}

    def create_member(self, service_from: date, outside_coverage: bool = False) -> str:
        self.counter += 1
        member_id = f"M{self.counter:08d}"
        dob_year = self.rng.randint(1950, 2012)
        dob_month = self.rng.randint(1, 12)
        dob_day = min(self.rng.randint(1, 28), 28)
        dob = date(dob_year, dob_month, dob_day)
        gender = self.rng.choice(["F", "M", "X"])

        if outside_coverage:
            coverage_start = service_from - timedelta(days=120)
            coverage_end = service_from - timedelta(days=1)
        else:
            coverage_start = service_from - timedelta(days=365)
            coverage_end = service_from + timedelta(days=365)

        row = {
            "member_id": member_id,
            "dob": dob.isoformat(),
            "gender": gender,
            "coverage_start": coverage_start.isoformat(),
            "coverage_end": coverage_end.isoformat(),
        }
        self.member_rows.append(row)
        self.member_index[member_id] = row
        return member_id


class ProviderFactory:
    def __init__(self) -> None:
        self.provider_rows = self._build_rows()
        self.provider_pool = [row["provider_npi"] for row in self.provider_rows]

    @staticmethod
    def _build_rows() -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        taxonomies = ["207Q00000X", "207R00000X", "261Q00000X", "208D00000X"]
        for idx in range(1, 41):
            npi = f"{8000000000 + idx}"
            rows.append(
                {
                    "provider_npi": npi,
                    "provider_name": f"SYNTH_PROVIDER_{idx:02d}",
                    "taxonomy": taxonomies[(idx - 1) % len(taxonomies)],
                }
            )
        return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate GCT-020 synthetic encounters dataset")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run_date", type=str, required=True, help="YYYY-MM-DD")
    return parser.parse_args()


def money_str(cents: int) -> str:
    return f"{cents / 100:.2f}"


def monday_of(input_date: date) -> date:
    return input_date - timedelta(days=input_date.weekday())


def build_batch_plan(run_date: date) -> List[BatchPlan]:
    week_01 = monday_of(run_date)
    week_starts = [week_01 + timedelta(weeks=i) for i in range(10)]
    incident_labels = {
        (2, "MEDICAID", "VENDOR_A"): "ONBOARDING_BLOCKERS",
        (6, "COMMERCIAL", "VENDOR_B"): "ELIGIBILITY_INCIDENT",
        (7, "COMMERCIAL", "VENDOR_C"): "DUP_REPLAY_INCIDENT",
        (10, "MEDICAID", "VENDOR_A"): "VOLUME_SPIKE",
    }

    plans: List[BatchPlan] = []
    for week_idx, week_start in enumerate(week_starts, start=1):
        week_label = f"W{week_idx:02d}"
        for lob in LOB_VALUES:
            for vendor in VENDOR_VALUES:
                batch_id = f"BATCH_{week_start.isoformat()}_{lob}_{vendor}"
                claim_target = 320 if (week_idx == 10 and lob == "MEDICAID" and vendor == "VENDOR_A") else 200
                storyline = incident_labels.get((week_idx, lob, vendor), "STABLE")
                plans.append(
                    BatchPlan(
                        week_label=week_label,
                        week_start=week_start,
                        lob=lob,
                        vendor=vendor,
                        batch_id=batch_id,
                        claim_target=claim_target,
                        storyline_label=storyline,
                    )
                )
    return plans


def generate_base_claim(
    *,
    rng: random.Random,
    plan: BatchPlan,
    claim_idx: int,
    claim_id: str,
    provider_pool: List[str],
    member_factory: MemberFactory,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    service_from = plan.week_start + timedelta(days=rng.randint(0, 4))
    service_to = service_from + timedelta(days=rng.randint(0, 2))
    adjudication_date = service_to + timedelta(days=rng.randint(10, 25))

    charge_cents = rng.randint(12_000, 95_000)
    allowed_cents = min(charge_cents, int(charge_cents * rng.uniform(0.55, 0.95)))
    paid_cents = min(allowed_cents, int(allowed_cents * rng.uniform(0.60, 1.00)))
    allowed_cents = max(allowed_cents, 100)
    paid_cents = max(paid_cents, 0)

    member_id = member_factory.create_member(service_from=service_from, outside_coverage=False)
    provider_npi = rng.choice(provider_pool)

    header = {
        "batch_id": plan.batch_id,
        "claim_id": claim_id,
        "member_id": member_id,
        "provider_npi": provider_npi,
        "lob": plan.lob,
        "vendor": plan.vendor,
        "service_from": service_from.isoformat(),
        "service_to": service_to.isoformat(),
        "total_charge": money_str(charge_cents),
        "total_allowed": money_str(allowed_cents),
        "total_paid": money_str(paid_cents),
        "adjudication_date": adjudication_date.isoformat(),
    }

    line = {
        "claim_id": claim_id,
        "line_id": f"L{claim_idx + 1:03d}",
        "proc_code": rng.choice(["99213", "99214", "87070", "93000", "71045"]),
        "dx_code": rng.choice(["E119", "I10", "J449", "M545", "R079"]),
        "units": str(rng.randint(1, 3)),
        "charge": money_str(charge_cents),
        "allowed": money_str(allowed_cents),
        "paid": money_str(paid_cents),
    }
    return header, line


def apply_onboarding_blockers(
    headers: List[Dict[str, str]],
    lines: List[Dict[str, str]],
    run_date: date,
) -> Dict[str, int]:
    line_by_claim = {row["claim_id"]: row for row in lines}
    rule_counts: Dict[str, int] = {}

    def mark(rule: str, count: int) -> None:
        rule_counts[rule] = count

    idx = {
        "R001": list(range(0, 10)),
        "R002": list(range(10, 15)),
        "R003": list(range(15, 25)),
        "R004": list(range(25, 30)),
        "R005": list(range(30, 40)),
        "R006": list(range(40, 50)),
        "R007": list(range(50, 60)),
        "R008": list(range(60, 70)),
        "R009": list(range(70, 80)),
    }

    for i in idx["R001"]:
        headers[i]["member_id"] = ""
    mark("R001", len(idx["R001"]))

    for i in idx["R002"]:
        original_claim_id = headers[i]["claim_id"]
        headers[i]["claim_id"] = ""
        line_by_claim.pop(original_claim_id, None)
    mark("R002", len(idx["R002"]))

    for i in idx["R003"]:
        headers[i]["provider_npi"] = ""
    mark("R003", len(idx["R003"]))

    for i in idx["R004"]:
        headers[i]["service_from"] = ""
    mark("R004", len(idx["R004"]))

    for i in idx["R005"]:
        headers[i]["provider_npi"] = "123456789"
    mark("R005", len(idx["R005"]))

    for i in idx["R006"]:
        headers[i]["provider_npi"] = "NPIABC1234"
    mark("R006", len(idx["R006"]))

    for i in idx["R007"]:
        headers[i]["provider_npi"] = RESERVED_NPI_NOT_FOUND
    mark("R007", len(idx["R007"]))

    for i in idx["R008"]:
        if headers[i]["service_from"]:
            service_from = date.fromisoformat(headers[i]["service_from"])
            headers[i]["service_to"] = (service_from - timedelta(days=1)).isoformat()
    mark("R008", len(idx["R008"]))

    for i in idx["R009"]:
        future_service_from = run_date + timedelta(days=8)
        headers[i]["service_from"] = future_service_from.isoformat()
        headers[i]["service_to"] = (future_service_from + timedelta(days=1)).isoformat()
    mark("R009", len(idx["R009"]))

    lines[:] = list(line_by_claim.values())
    return rule_counts


def apply_eligibility_incident(
    headers: List[Dict[str, str]],
    member_index: Dict[str, Dict[str, str]],
) -> int:
    impacted = 0
    for i in range(6):
        member_id = headers[i]["member_id"]
        service_from = date.fromisoformat(headers[i]["service_from"])
        member_row = member_index[member_id]
        member_row["coverage_start"] = (service_from - timedelta(days=120)).isoformat()
        member_row["coverage_end"] = (service_from - timedelta(days=1)).isoformat()
        impacted += 1
    return impacted


def apply_dup_replay_incident(
    headers: List[Dict[str, str]],
    lines: List[Dict[str, str]],
    member_factory: MemberFactory,
) -> Dict[str, int]:
    line_by_claim = {row["claim_id"]: row for row in lines}

    duplicate_pairs = [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]
    for left, right in duplicate_pairs:
        headers[right]["member_id"] = headers[left]["member_id"]
        headers[right]["provider_npi"] = headers[left]["provider_npi"]
        headers[right]["service_from"] = headers[left]["service_from"]
        headers[right]["service_to"] = headers[left]["service_to"]
        headers[right]["total_charge"] = headers[left]["total_charge"]
        headers[right]["total_allowed"] = headers[left]["total_allowed"]
        headers[right]["total_paid"] = headers[left]["total_paid"]

        right_claim_id = headers[right]["claim_id"]
        left_claim_id = headers[left]["claim_id"]
        left_line = line_by_claim[left_claim_id]
        line_by_claim[right_claim_id] = {
            **left_line,
            "claim_id": right_claim_id,
            "line_id": line_by_claim[right_claim_id]["line_id"],
        }

    def set_line_financial(claim_idx_range: range, *, charge_offset: int, allowed_offset: int, paid_offset: int) -> None:
        for idx in claim_idx_range:
            claim_id = headers[idx]["claim_id"]
            line = line_by_claim[claim_id]
            charge_cents = int(round(float(line["charge"]) * 100))
            allowed_cents = int(round(float(line["allowed"]) * 100))
            paid_cents = int(round(float(line["paid"]) * 100))

            charge_cents = max(100, charge_cents + charge_offset)
            allowed_cents = max(100, allowed_cents + allowed_offset)
            paid_cents = max(0, paid_cents + paid_offset)

            line["charge"] = money_str(charge_cents)
            line["allowed"] = money_str(allowed_cents)
            line["paid"] = money_str(paid_cents)

            headers[idx]["total_charge"] = line["charge"]
            headers[idx]["total_allowed"] = line["allowed"]
            headers[idx]["total_paid"] = line["paid"]

    for idx in range(20, 40):
        claim_id = headers[idx]["claim_id"]
        line = line_by_claim[claim_id]
        allowed_cents = int(round(float(line["allowed"]) * 100))
        line["paid"] = money_str(allowed_cents + 100)
        headers[idx]["total_paid"] = line["paid"]

    for idx in range(40, 60):
        claim_id = headers[idx]["claim_id"]
        line = line_by_claim[claim_id]
        charge_cents = int(round(float(line["charge"]) * 100))
        line["allowed"] = money_str(charge_cents + 100)
        headers[idx]["total_allowed"] = line["allowed"]

    for idx in range(60, 80):
        claim_id = headers[idx]["claim_id"]
        line_by_claim[claim_id]["proc_code"] = ""

    for idx in range(80, 100):
        claim_id = headers[idx]["claim_id"]
        line_by_claim[claim_id]["dx_code"] = ""

    lines[:] = list(line_by_claim.values())
    return {
        "R011": 5,
        "R012": 20,
        "R013": 20,
        "R014": 20,
        "R015": 20,
    }


def claim_key(header: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    total_charge = f"{float(header['total_charge']):.2f}"
    return (
        header["batch_id"],
        header["member_id"],
        header["provider_npi"],
        header["service_from"],
        total_charge,
    )


def write_csv(path: Path, columns: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def stable_file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def verify_acceptance(
    run_date: date,
    headers: List[Dict[str, str]],
    lines: List[Dict[str, str]],
    members: List[Dict[str, str]],
    story_rows: List[Dict[str, str]],
    providers: List[Dict[str, str]],
    onboarding_batch_id: str,
    eligibility_batch_id: str,
    dup_batch_id: str,
    spike_batch_id: str,
) -> Dict[str, bool]:
    checks: Dict[str, bool] = {}

    checks["60_batches"] = len({r["batch_id"] for r in headers}) == 60
    checks["10_week_starts"] = len(
        {
            monday_of(date.fromisoformat(r["service_from"])).isoformat()
            for r in headers
            if r["service_from"]
        }
    ) == 10
    checks["2_lobs"] = {r["lob"] for r in headers} == set(LOB_VALUES)
    checks["3_vendors"] = {r["vendor"] for r in headers} == set(VENDOR_VALUES)
    checks["one_batch_per_week_lob_vendor"] = all(
        len({row["batch_id"] for row in story_rows if row["week_start"] == w and row["lob"] == l and row["vendor"] == v}) == 1
        for w in {r["week_start"] for r in story_rows}
        for l in LOB_VALUES
        for v in VENDOR_VALUES
    )

    weekly_counts = Counter((r["batch_id"] for r in headers))
    checks["spike_batch_320"] = weekly_counts[spike_batch_id] == 320

    medicaid_vendor_a_batches = [
        row for row in story_rows if row["lob"] == "MEDICAID" and row["vendor"] == "VENDOR_A"
    ]
    medicaid_vendor_a_batches.sort(key=lambda row: row["week_start"])
    for idx, row in enumerate(medicaid_vendor_a_batches, start=1):
        count = weekly_counts[row["batch_id"]]
        if idx == 10:
            checks[f"{row['batch_id']}_count"] = count == 320
        elif 2 <= idx <= 9:
            checks[f"{row['batch_id']}_count"] = count == 200

    onboarding_headers = [r for r in headers if r["batch_id"] == onboarding_batch_id]

    checks["R001_min_10"] = sum(1 for r in onboarding_headers if r["member_id"] == "") >= 10
    checks["R002_min_5"] = sum(1 for r in onboarding_headers if r["claim_id"] == "") >= 5
    checks["R002_no_lines"] = sum(1 for r in lines if r["claim_id"] == "") == 0
    checks["R003_min_10"] = sum(1 for r in onboarding_headers if r["provider_npi"] == "") >= 10
    checks["R004_min_5"] = sum(1 for r in onboarding_headers if r["service_from"] == "") >= 5
    checks["R005_min_10"] = sum(
        1 for r in onboarding_headers if len(r["provider_npi"]) == 9 and r["provider_npi"].isdigit()
    ) >= 10
    checks["R006_min_10"] = sum(
        1 for r in onboarding_headers if r["provider_npi"] and (not r["provider_npi"].isdigit())
    ) >= 10
    checks["R007_min_10"] = sum(1 for r in onboarding_headers if r["provider_npi"] == RESERVED_NPI_NOT_FOUND) >= 10
    checks["R008_min_10"] = sum(
        1
        for r in onboarding_headers
        if r["service_from"]
        and r["service_to"]
        and date.fromisoformat(r["service_to"]) < date.fromisoformat(r["service_from"])
    ) >= 10
    checks["R009_min_10"] = sum(
        1
        for r in onboarding_headers
        if r["service_from"] and date.fromisoformat(r["service_from"]) > run_date
    ) >= 10

    eligibility_headers = [r for r in headers if r["batch_id"] == eligibility_batch_id]
    member_lookup = {m["member_id"]: m for m in members}
    checks["R010_exact_6"] = sum(
        1
        for r in eligibility_headers
        if r["member_id"] in member_lookup
        and r["service_from"]
        and date.fromisoformat(r["service_from"]) > date.fromisoformat(member_lookup[r["member_id"]]["coverage_end"])
    ) == 6

    dup_headers = [r for r in headers if r["batch_id"] == dup_batch_id]
    dup_key_counter = Counter(claim_key(row) for row in dup_headers)
    checks["R011_exact_5_keys"] = sum(1 for _, c in dup_key_counter.items() if c == 2) == 5

    dup_lines = [row for row in lines if row["claim_id"] in {h["claim_id"] for h in dup_headers if h["claim_id"]}]
    checks["R012_exact_20"] = sum(1 for r in dup_lines if float(r["paid"]) > float(r["allowed"])) == 20
    checks["R013_exact_20"] = sum(1 for r in dup_lines if float(r["allowed"]) > float(r["charge"])) == 20
    checks["R014_exact_20"] = sum(1 for r in dup_lines if r["proc_code"] == "") == 20
    checks["R015_exact_20"] = sum(1 for r in dup_lines if r["dx_code"] == "") == 20

    checks["story_map_60_rows"] = len(story_rows) == 60
    checks["story_labels"] = {
        "ONBOARDING_BLOCKERS",
        "STABLE",
        "ELIGIBILITY_INCIDENT",
        "DUP_REPLAY_INCIDENT",
        "VOLUME_SPIKE",
    }.issubset({r["storyline_label"] for r in story_rows})

    checks["reserved_npi_excluded"] = RESERVED_NPI_NOT_FOUND not in {r["provider_npi"] for r in providers}

    for colset_name, rows, cols in [
        ("header_schema", headers, set(HEADER_COLUMNS)),
        ("line_schema", lines, set(LINES_COLUMNS)),
        ("member_schema", members, set(MEMBERS_COLUMNS)),
        ("provider_schema", providers, set(PROVIDERS_COLUMNS)),
        ("story_schema", story_rows, set(STORY_COLUMNS)),
    ]:
        checks[colset_name] = all(set(row.keys()) == cols for row in rows)

    checks["amounts_2dp_headers"] = all(
        money_field.count(".") == 1 and len(money_field.split(".")[1]) == 2
        for row in headers
        for money_field in (row["total_charge"], row["total_allowed"], row["total_paid"])
    )
    checks["amounts_2dp_lines"] = all(
        money_field.count(".") == 1 and len(money_field.split(".")[1]) == 2
        for row in lines
        for money_field in (row["charge"], row["allowed"], row["paid"])
    )
    checks["story_covers_all_batches"] = {r["batch_id"] for r in story_rows} == {r["batch_id"] for r in headers}

    return checks


def build_dataset(seed: int, run_date: date, root: Path) -> None:
    rng = random.Random(seed)

    data_raw_dir = root / "data_raw"
    outputs_dir = root / "outputs"

    provider_factory = ProviderFactory()
    member_factory = MemberFactory(rng)

    plans = build_batch_plan(run_date)
    headers: List[Dict[str, str]] = []
    lines: List[Dict[str, str]] = []
    story_rows: List[Dict[str, str]] = []

    onboarding_batch_id = ""
    eligibility_batch_id = ""
    dup_batch_id = ""
    spike_batch_id = ""

    for plan in plans:
        batch_headers: List[Dict[str, str]] = []
        batch_lines: List[Dict[str, str]] = []

        for claim_idx in range(plan.claim_target):
            claim_id = f"CLM_{plan.week_label}_{plan.lob}_{plan.vendor}_{claim_idx + 1:04d}"
            header, line = generate_base_claim(
                rng=rng,
                plan=plan,
                claim_idx=claim_idx,
                claim_id=claim_id,
                provider_pool=provider_factory.provider_pool,
                member_factory=member_factory,
            )
            batch_headers.append(header)
            batch_lines.append(line)

        if plan.storyline_label == "ONBOARDING_BLOCKERS":
            onboarding_batch_id = plan.batch_id
            apply_onboarding_blockers(batch_headers, batch_lines, run_date)
        elif plan.storyline_label == "ELIGIBILITY_INCIDENT":
            eligibility_batch_id = plan.batch_id
            apply_eligibility_incident(batch_headers, member_factory.member_index)
        elif plan.storyline_label == "DUP_REPLAY_INCIDENT":
            dup_batch_id = plan.batch_id
            apply_dup_replay_incident(batch_headers, batch_lines, member_factory)
        elif plan.storyline_label == "VOLUME_SPIKE":
            spike_batch_id = plan.batch_id

        headers.extend(batch_headers)
        lines.extend(batch_lines)
        story_rows.append(
            {
                "week_start": plan.week_start.isoformat(),
                "lob": plan.lob,
                "vendor": plan.vendor,
                "batch_id": plan.batch_id,
                "storyline_label": plan.storyline_label,
            }
        )

    members = member_factory.member_rows
    providers = provider_factory.provider_rows

    checks = verify_acceptance(
        run_date=run_date,
        headers=headers,
        lines=lines,
        members=members,
        story_rows=story_rows,
        providers=providers,
        onboarding_batch_id=onboarding_batch_id,
        eligibility_batch_id=eligibility_batch_id,
        dup_batch_id=dup_batch_id,
        spike_batch_id=spike_batch_id,
    )

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"Acceptance checks failed: {', '.join(sorted(failed))}")

    write_csv(data_raw_dir / "encounters_header.csv", HEADER_COLUMNS, headers)
    write_csv(data_raw_dir / "encounters_lines.csv", LINES_COLUMNS, lines)
    write_csv(data_raw_dir / "reference_members.csv", MEMBERS_COLUMNS, members)
    write_csv(data_raw_dir / "reference_providers.csv", PROVIDERS_COLUMNS, providers)
    write_csv(outputs_dir / "story_map.csv", STORY_COLUMNS, story_rows)

    receipt_path = outputs_dir / "dataset_receipt.md"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    onboarding_headers = [r for r in headers if r["batch_id"] == onboarding_batch_id]
    eligibility_headers = [r for r in headers if r["batch_id"] == eligibility_batch_id]
    dup_headers = [r for r in headers if r["batch_id"] == dup_batch_id]
    dup_claims = {r["claim_id"] for r in dup_headers if r["claim_id"]}
    dup_lines = [r for r in lines if r["claim_id"] in dup_claims]

    outside_coverage = 0
    member_lookup = {m["member_id"]: m for m in members}
    for row in eligibility_headers:
        member = member_lookup[row["member_id"]]
        if date.fromisoformat(row["service_from"]) > date.fromisoformat(member["coverage_end"]):
            outside_coverage += 1

    dup_key_counter = Counter(claim_key(row) for row in dup_headers)
    dup_key_count = sum(1 for _, c in dup_key_counter.items() if c == 2)

    checklist = [
        ("60 batches present", checks["60_batches"]),
        ("10 week_start values", checks["10_week_starts"]),
        ("Exactly 1 batch per (week_start,lob,vendor)", checks["one_batch_per_week_lob_vendor"]),
        ("2 LOBs and 3 vendors", checks["2_lobs"] and checks["3_vendors"]),
        ("W10 MEDICAID VENDOR_A = 320 claims", checks["spike_batch_320"]),
        ("W02 blockers minimum counts met (R001-R009)", all(checks[k] for k in [
            "R001_min_10", "R002_min_5", "R002_no_lines", "R003_min_10", "R004_min_5", "R005_min_10", "R006_min_10", "R007_min_10", "R008_min_10", "R009_min_10"
        ])),
        ("W06 eligibility incident exactly 6 claims outside coverage", checks["R010_exact_6"]),
        ("W07 duplicate replay exactly 5 duplicate claim_keys", checks["R011_exact_5_keys"]),
        ("W07 line injections exact counts R012-R015", all(checks[k] for k in ["R012_exact_20", "R013_exact_20", "R014_exact_20", "R015_exact_20"])),
        ("Story map has one row per batch and required labels", checks["story_map_60_rows"] and checks["story_labels"]),
        ("Story map covers every batch_id", checks["story_covers_all_batches"]),
        ("Reserved NPI 9999999999 excluded from reference_providers", checks["reserved_npi_excluded"]),
        ("All money fields stable at two decimals", checks["amounts_2dp_headers"] and checks["amounts_2dp_lines"]),
    ]

    file_digests = {
        "data_raw/encounters_header.csv": stable_file_digest(data_raw_dir / "encounters_header.csv"),
        "data_raw/encounters_lines.csv": stable_file_digest(data_raw_dir / "encounters_lines.csv"),
        "data_raw/reference_members.csv": stable_file_digest(data_raw_dir / "reference_members.csv"),
        "data_raw/reference_providers.csv": stable_file_digest(data_raw_dir / "reference_providers.csv"),
        "outputs/story_map.csv": stable_file_digest(outputs_dir / "story_map.csv"),
    }

    total_claims = len(headers)
    total_lines = len(lines)

    lines_out = [
        "# Dataset Receipt — GCT-020",
        "",
        f"- Generated at: {run_date.isoformat()}T00:00:00Z",
        f"- seed: {seed}",
        f"- run_date: {run_date.isoformat()}",
        f"- total_batches: {len(plans)}",
        f"- total_claims: {total_claims}",
        f"- total_lines: {total_lines}",
        f"- total_members: {len(members)}",
        f"- total_providers: {len(providers)}",
        "",
        "## Incident batches",
        f"- ONBOARDING_BLOCKERS: {onboarding_batch_id}",
        f"  - demonstrates R001-R009 blockers with disjoint claim sets",
        f"- ELIGIBILITY_INCIDENT: {eligibility_batch_id}",
        f"  - demonstrates R010 with exactly {outside_coverage} claims outside coverage",
        f"- DUP_REPLAY_INCIDENT: {dup_batch_id}",
        f"  - demonstrates R011 duplicate claim_keys = {dup_key_count}",
        f"  - demonstrates line-level injections R012={sum(1 for r in dup_lines if float(r['paid']) > float(r['allowed']))}, R013={sum(1 for r in dup_lines if float(r['allowed']) > float(r['charge']))}, R014={sum(1 for r in dup_lines if r['proc_code'] == '')}, R015={sum(1 for r in dup_lines if r['dx_code'] == '')}",
        f"- VOLUME_SPIKE: {spike_batch_id}",
        "  - demonstrates R903-ready spike at 320 claims",
        "",
        "## Acceptance checklist",
    ]

    for title, passed in checklist:
        icon = "✅" if passed else "❌"
        lines_out.append(f"- {icon} {title}")

    lines_out.extend([
        "",
        "## Determinism fingerprints (sha256)",
    ])
    for relative_path, digest in file_digests.items():
        lines_out.append(f"- {relative_path}: {digest}")

    lines_out.extend([
        "",
        "## Raw verification payload",
        "```json",
        json.dumps(checks, indent=2, sort_keys=True),
        "```",
    ])

    receipt_path.write_text("\n".join(lines_out), encoding="utf-8")


def main() -> None:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date)
    project_root = Path(__file__).resolve().parents[1]
    build_dataset(seed=args.seed, run_date=run_date, root=project_root)


if __name__ == "__main__":
    main()
