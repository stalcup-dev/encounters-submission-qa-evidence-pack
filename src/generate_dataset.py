
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple

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
WEEK_COUNT = 10

START_WEEK = date(2026, 2, 23)
LOCKED_RUN_DATE = date(2026, 5, 10)
BATCH_ID_FORMAT = "BATCH_<YYYYMMDD>_<VENDOR>_<LOB>_W<NN>"
RESERVED_NPI_NOT_FOUND = "9999999999"


@dataclass(frozen=True)
class BatchPlan:
    week_idx: int
    week_label: str
    week_start: date
    lob: str
    vendor: str
    batch_id: str
    claim_target: int
    storyline_label: str


@dataclass
class MemberRecord:
    member_id: str
    dob: date
    gender: str
    coverage_start: date
    coverage_end: date

    def to_row(self) -> Dict[str, str]:
        return {
            "member_id": self.member_id,
            "dob": self.dob.isoformat(),
            "gender": self.gender,
            "coverage_start": self.coverage_start.isoformat(),
            "coverage_end": self.coverage_end.isoformat(),
        }


@dataclass
class ClaimRecord:
    batch_id: str
    claim_id: str
    member_id: str
    provider_npi: str
    lob: str
    vendor: str
    service_from: Optional[date]
    service_to: Optional[date]
    total_charge_cents: int
    total_allowed_cents: int
    total_paid_cents: int
    adjudication_date: Optional[date]

    def to_row(self) -> Dict[str, str]:
        return {
            "batch_id": self.batch_id,
            "claim_id": self.claim_id,
            "member_id": self.member_id,
            "provider_npi": self.provider_npi,
            "lob": self.lob,
            "vendor": self.vendor,
            "service_from": self.service_from.isoformat() if self.service_from else "",
            "service_to": self.service_to.isoformat() if self.service_to else "",
            "total_charge": money_str(self.total_charge_cents),
            "total_allowed": money_str(self.total_allowed_cents),
            "total_paid": money_str(self.total_paid_cents),
            "adjudication_date": self.adjudication_date.isoformat() if self.adjudication_date else "",
        }


@dataclass
class LineRecord:
    claim_id: str
    line_id: str
    proc_code: str
    dx_code: str
    units: int
    charge_cents: int
    allowed_cents: int
    paid_cents: int

    def to_row(self) -> Dict[str, str]:
        return {
            "claim_id": self.claim_id,
            "line_id": self.line_id,
            "proc_code": self.proc_code,
            "dx_code": self.dx_code,
            "units": str(self.units),
            "charge": money_str(self.charge_cents),
            "allowed": money_str(self.allowed_cents),
            "paid": money_str(self.paid_cents),
        }


class MemberFactory:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.counter = 0
        self.member_rows: List[MemberRecord] = []
        self.member_index: Dict[str, MemberRecord] = {}

    def create(self, service_from: date) -> str:
        self.counter += 1
        member_id = f"M{self.counter:08d}"
        dob = date(
            self.rng.randint(1950, 2012),
            self.rng.randint(1, 12),
            self.rng.randint(1, 28),
        )
        gender = self.rng.choice(["F", "M", "X"])
        row = MemberRecord(
            member_id=member_id,
            dob=dob,
            gender=gender,
            coverage_start=service_from - timedelta(days=365),
            coverage_end=service_from + timedelta(days=365),
        )
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
        taxonomies = ["207Q00000X", "207R00000X", "261Q00000X", "208D00000X", "163W00000X"]
        for idx in range(1, 61):
            npi = f"{8100000000 + idx}"
            rows.append(
                {
                    "provider_npi": npi,
                    "provider_name": f"SYNTH_PROVIDER_{idx:03d}",
                    "taxonomy": taxonomies[(idx - 1) % len(taxonomies)],
                }
            )
        return rows


class IdFactory:
    def __init__(self) -> None:
        self.line_counter = 0
        self.clone_counter = 0

    def next_line_id(self) -> str:
        self.line_counter += 1
        return f"LN{self.line_counter:07d}"

    def next_clone_claim_id(self, source_claim_id: str) -> str:
        self.clone_counter += 1
        return f"{source_claim_id}_CLONE{self.clone_counter:03d}"


def money_str(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents_abs = abs(cents)
    return f"{sign}{cents_abs // 100}.{cents_abs % 100:02d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate story synthetic encounters dataset v1")
    parser.add_argument("--seed", required=True, type=int, help="Deterministic RNG seed")
    parser.add_argument("--run_date", required=True, type=str, help="Must be 2026-05-10")
    parser.add_argument("--out_dir", required=True, type=str, help="Output root directory")
    return parser.parse_args()


def make_batch_id(week_start: date, vendor: str, lob: str, week_label: str) -> str:
    return f"BATCH_{week_start.strftime('%Y%m%d')}_{vendor}_{lob}_{week_label}"


def build_batch_plan() -> List[BatchPlan]:
    incident_labels = {
        (2, "MEDICAID", "VENDOR_A"): "ONBOARDING_BLOCKERS",
        (6, "COMMERCIAL", "VENDOR_B"): "ELIGIBILITY_INCIDENT",
        (7, "COMMERCIAL", "VENDOR_C"): "DUP_REPLAY_INCIDENT",
        (10, "MEDICAID", "VENDOR_A"): "VOLUME_SPIKE",
    }

    plans: List[BatchPlan] = []
    for week_idx in range(1, WEEK_COUNT + 1):
        week_start = START_WEEK + timedelta(weeks=week_idx - 1)
        week_label = f"W{week_idx:02d}"
        for lob in LOB_VALUES:
            for vendor in VENDOR_VALUES:
                batch_id = make_batch_id(week_start, vendor, lob, week_label)
                claim_target = 320 if (week_idx == 10 and lob == "MEDICAID" and vendor == "VENDOR_A") else 200
                storyline_label = incident_labels.get((week_idx, lob, vendor), "STABLE")
                plans.append(
                    BatchPlan(
                        week_idx=week_idx,
                        week_label=week_label,
                        week_start=week_start,
                        lob=lob,
                        vendor=vendor,
                        batch_id=batch_id,
                        claim_target=claim_target,
                        storyline_label=storyline_label,
                    )
                )
    return plans


def generate_clean_batch(
    *,
    rng: random.Random,
    plan: BatchPlan,
    member_factory: MemberFactory,
    provider_pool: List[str],
    id_factory: IdFactory,
) -> Tuple[List[ClaimRecord], Dict[str, LineRecord]]:
    claims: List[ClaimRecord] = []
    lines_by_claim_id: Dict[str, LineRecord] = {}

    proc_pool = ["99213", "99214", "93000", "87070", "71045", "36415"]
    dx_pool = ["I10", "E119", "J449", "M545", "R079", "K219"]

    for claim_idx in range(1, plan.claim_target + 1):
        claim_id = f"CLM_{plan.week_label}_{plan.vendor}_{plan.lob}_{claim_idx:04d}"

        service_from = plan.week_start + timedelta(days=rng.randint(0, 4))
        service_to = service_from + timedelta(days=rng.randint(0, 2))
        adjudication_date = service_to + timedelta(days=rng.randint(7, 21))

        charge_cents = rng.randint(20000, 125000)
        allowed_delta = rng.randint(500, 15000)
        allowed_cents = max(100, charge_cents - allowed_delta)
        paid_delta = rng.randint(0, min(allowed_cents - 1, 5000))
        paid_cents = max(0, allowed_cents - paid_delta)

        member_id = member_factory.create(service_from)
        provider_npi = rng.choice(provider_pool)

        claim = ClaimRecord(
            batch_id=plan.batch_id,
            claim_id=claim_id,
            member_id=member_id,
            provider_npi=provider_npi,
            lob=plan.lob,
            vendor=plan.vendor,
            service_from=service_from,
            service_to=service_to,
            total_charge_cents=charge_cents,
            total_allowed_cents=allowed_cents,
            total_paid_cents=paid_cents,
            adjudication_date=adjudication_date,
        )
        claims.append(claim)

        line = LineRecord(
            claim_id=claim_id,
            line_id=id_factory.next_line_id(),
            proc_code=rng.choice(proc_pool),
            dx_code=rng.choice(dx_pool),
            units=rng.randint(1, 3),
            charge_cents=charge_cents,
            allowed_cents=allowed_cents,
            paid_cents=paid_cents,
        )
        lines_by_claim_id[claim_id] = line

    return claims, lines_by_claim_id


def claim_key(claim: ClaimRecord) -> Tuple[str, str, str, str, str]:
    service_from = claim.service_from.isoformat() if claim.service_from else ""
    return (
        claim.batch_id,
        claim.member_id,
        claim.provider_npi,
        service_from,
        money_str(claim.total_charge_cents),
    )


def ordered_lines_for_claims(claims: List[ClaimRecord], lines_by_claim_id: Dict[str, LineRecord]) -> List[LineRecord]:
    ordered: List[LineRecord] = []
    for claim in claims:
        if claim.claim_id and claim.claim_id in lines_by_claim_id:
            ordered.append(lines_by_claim_id[claim.claim_id])
    return ordered

def apply_w02_onboarding_blockers(
    claims: List[ClaimRecord],
    lines_by_claim_id: Dict[str, LineRecord],
    run_date: date,
) -> Dict[str, object]:
    # Exact disjoint index allocation for R001-R009.
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

    manifest_rules: Dict[str, object] = {}

    # R001 NULL_MEMBER_ID
    r001_claim_ids: List[str] = []
    for i in idx["R001"]:
        claims[i].member_id = ""
        r001_claim_ids.append(claims[i].claim_id)
    manifest_rules["R001_NULL_MEMBER_ID"] = {"count": len(r001_claim_ids), "claim_ids": r001_claim_ids}

    # R002 NULL_CLAIM_ID (blank claim_id rows have no lines)
    r002_row_indices: List[int] = []
    for i in idx["R002"]:
        old_claim_id = claims[i].claim_id
        lines_by_claim_id.pop(old_claim_id, None)
        claims[i].claim_id = ""
        r002_row_indices.append(i)
    manifest_rules["R002_NULL_CLAIM_ID"] = {"count": len(r002_row_indices), "header_row_indices": r002_row_indices}

    # R003 NULL_PROVIDER_NPI
    r003_claim_ids: List[str] = []
    for i in idx["R003"]:
        claims[i].provider_npi = ""
        r003_claim_ids.append(claims[i].claim_id)
    manifest_rules["R003_NULL_PROVIDER_NPI"] = {"count": len(r003_claim_ids), "claim_ids": r003_claim_ids}

    # R004 NULL_SERVICE_FROM
    r004_claim_ids: List[str] = []
    for i in idx["R004"]:
        claims[i].service_from = None
        r004_claim_ids.append(claims[i].claim_id)
    manifest_rules["R004_NULL_SERVICE_FROM"] = {"count": len(r004_claim_ids), "claim_ids": r004_claim_ids}

    # R005 NPI_BAD_LENGTH
    r005_claim_ids: List[str] = []
    for i in idx["R005"]:
        claims[i].provider_npi = "123456789"
        r005_claim_ids.append(claims[i].claim_id)
    manifest_rules["R005_NPI_BAD_LENGTH"] = {"count": len(r005_claim_ids), "claim_ids": r005_claim_ids}

    # R006 NPI_NOT_NUMERIC
    r006_claim_ids: List[str] = []
    for i in idx["R006"]:
        claims[i].provider_npi = "NPIABC1234"
        r006_claim_ids.append(claims[i].claim_id)
    manifest_rules["R006_NPI_NOT_NUMERIC"] = {"count": len(r006_claim_ids), "claim_ids": r006_claim_ids}

    # R007 NPI_NOT_FOUND (reserved value)
    r007_claim_ids: List[str] = []
    for i in idx["R007"]:
        claims[i].provider_npi = RESERVED_NPI_NOT_FOUND
        r007_claim_ids.append(claims[i].claim_id)
    manifest_rules["R007_NPI_NOT_FOUND"] = {"count": len(r007_claim_ids), "claim_ids": r007_claim_ids}

    # R008 SERVICE_TO_BEFORE_FROM
    r008_claim_ids: List[str] = []
    for i in idx["R008"]:
        if claims[i].service_from is None:
            raise AssertionError("R008 source claim unexpectedly missing service_from.")
        claims[i].service_to = claims[i].service_from - timedelta(days=1)
        r008_claim_ids.append(claims[i].claim_id)
    manifest_rules["R008_SERVICE_TO_BEFORE_FROM"] = {"count": len(r008_claim_ids), "claim_ids": r008_claim_ids}

    # R009 FUTURE_SERVICE_DATE (future relative to locked RUN_DATE)
    r009_claim_ids: List[str] = []
    future_service_from = run_date + timedelta(days=2)
    for i in idx["R009"]:
        claims[i].service_from = future_service_from
        claims[i].service_to = future_service_from + timedelta(days=1)
        r009_claim_ids.append(claims[i].claim_id)
    manifest_rules["R009_FUTURE_SERVICE_DATE"] = {"count": len(r009_claim_ids), "claim_ids": r009_claim_ids}

    return {
        "rule_counts": {
            "R001": 10,
            "R002": 5,
            "R003": 10,
            "R004": 5,
            "R005": 10,
            "R006": 10,
            "R007": 10,
            "R008": 10,
            "R009": 10,
        },
        "rules": manifest_rules,
    }


def apply_w06_eligibility_incident(
    claims: List[ClaimRecord],
    member_index: Dict[str, MemberRecord],
) -> Dict[str, object]:
    impacted_claim_ids: List[str] = []
    for i in range(6):
        claim = claims[i]
        if not claim.service_from:
            raise AssertionError("Eligibility incident source claim unexpectedly missing service_from.")
        member = member_index[claim.member_id]
        member.coverage_start = claim.service_from - timedelta(days=120)
        member.coverage_end = claim.service_from - timedelta(days=1)
        impacted_claim_ids.append(claim.claim_id)
    return {
        "rule_counts": {"R010": 6},
        "rules": {
            "R010_SERVICE_OUTSIDE_COVERAGE": {
                "count": 6,
                "claim_ids": impacted_claim_ids,
            }
        },
    }


def apply_w07_duplicate_and_line_incidents(
    claims: List[ClaimRecord],
    lines_by_claim_id: Dict[str, LineRecord],
    id_factory: IdFactory,
) -> Dict[str, object]:
    if len(claims) != 200:
        raise AssertionError("W07 duplicate incident expects exactly 200 baseline claims.")

    source_claims = claims[0:5]
    removed_claims = claims[-5:]
    removed_claim_ids = {c.claim_id for c in removed_claims}

    # Remove five clean claims so cloned rows can replace them, keeping batch size at 200.
    claims[:] = [c for c in claims if c.claim_id not in removed_claim_ids]
    for removed_claim_id in removed_claim_ids:
        lines_by_claim_id.pop(removed_claim_id, None)

    source_clone_pairs: List[Dict[str, str]] = []
    clone_claim_ids: List[str] = []
    source_claim_ids: List[str] = []

    for source in source_claims:
        source_claim_ids.append(source.claim_id)
        clone_claim_id = id_factory.next_clone_claim_id(source.claim_id)

        clone_claim = ClaimRecord(
            batch_id=source.batch_id,
            claim_id=clone_claim_id,
            member_id=source.member_id,
            provider_npi=source.provider_npi,
            lob=source.lob,
            vendor=source.vendor,
            service_from=source.service_from,
            service_to=source.service_to,
            total_charge_cents=source.total_charge_cents,
            total_allowed_cents=source.total_allowed_cents,
            total_paid_cents=source.total_paid_cents,
            adjudication_date=source.adjudication_date,
        )
        claims.append(clone_claim)

        source_line = lines_by_claim_id[source.claim_id]
        clone_line = LineRecord(
            claim_id=clone_claim_id,
            line_id=id_factory.next_line_id(),
            proc_code=source_line.proc_code,
            dx_code=source_line.dx_code,
            units=source_line.units,
            charge_cents=source_line.charge_cents,
            allowed_cents=source_line.allowed_cents,
            paid_cents=source_line.paid_cents,
        )
        lines_by_claim_id[clone_claim_id] = clone_line

        clone_claim_ids.append(clone_claim_id)
        source_clone_pairs.append({"source_claim_id": source.claim_id, "clone_claim_id": clone_claim_id})

    if len(claims) != 200:
        raise AssertionError("W07 duplicate construction did not preserve 200-claim batch size.")

    dup_participant_ids = source_claim_ids + clone_claim_ids
    dup_participant_id_set = set(dup_participant_ids)
    eligible_for_line_rules = [c for c in claims if c.claim_id not in dup_participant_id_set]
    if len(eligible_for_line_rules) < 80:
        raise AssertionError("Not enough clean claims available for disjoint R012-R015 line injections.")

    r012_claims = eligible_for_line_rules[0:20]
    r013_claims = eligible_for_line_rules[20:40]
    r014_claims = eligible_for_line_rules[40:60]
    r015_claims = eligible_for_line_rules[60:80]

    r012_line_refs: List[Dict[str, str]] = []
    for claim in r012_claims:
        line = lines_by_claim_id[claim.claim_id]
        line.paid_cents = line.allowed_cents + 100
        claim.total_paid_cents = line.paid_cents
        r012_line_refs.append({"claim_id": claim.claim_id, "line_id": line.line_id})

    r013_line_refs: List[Dict[str, str]] = []
    for claim in r013_claims:
        line = lines_by_claim_id[claim.claim_id]
        line.allowed_cents = line.charge_cents + 100
        claim.total_allowed_cents = line.allowed_cents
        r013_line_refs.append({"claim_id": claim.claim_id, "line_id": line.line_id})

    r014_line_refs: List[Dict[str, str]] = []
    for claim in r014_claims:
        line = lines_by_claim_id[claim.claim_id]
        line.proc_code = ""
        r014_line_refs.append({"claim_id": claim.claim_id, "line_id": line.line_id})

    r015_line_refs: List[Dict[str, str]] = []
    for claim in r015_claims:
        line = lines_by_claim_id[claim.claim_id]
        line.dx_code = ""
        r015_line_refs.append({"claim_id": claim.claim_id, "line_id": line.line_id})

    return {
        "rule_counts": {"R011": 10, "R012": 20, "R013": 20, "R014": 20, "R015": 20},
        "rules": {
            "R011_DUP_CLAIM_KEY": {
                "duplicate_key_count": 5,
                "participant_claim_ids": dup_participant_ids,
                "source_clone_pairs": source_clone_pairs,
                "removed_claim_count": 5,
            },
            "R012_PAID_GT_ALLOWED": {"count": 20, "line_refs": r012_line_refs},
            "R013_ALLOWED_GT_CHARGE": {"count": 20, "line_refs": r013_line_refs},
            "R014_NULL_PROC": {"count": 20, "line_refs": r014_line_refs},
            "R015_NULL_DX": {"count": 20, "line_refs": r015_line_refs},
        },
    }

def evaluate_rule_counts(
    claims: List[ClaimRecord],
    lines: List[LineRecord],
    provider_npis: set[str],
    member_lookup: Dict[str, MemberRecord],
    run_date: date,
) -> Dict[str, int]:
    counts = {f"R{i:03d}": 0 for i in range(1, 16)}

    key_to_claim_ids: Dict[Tuple[str, str, str, str, str], List[str]] = defaultdict(list)

    for claim in claims:
        if claim.member_id == "":
            counts["R001"] += 1
        if claim.claim_id == "":
            counts["R002"] += 1
        if claim.provider_npi == "":
            counts["R003"] += 1
        if claim.service_from is None:
            counts["R004"] += 1

        if claim.provider_npi:
            if claim.provider_npi.isdigit() and len(claim.provider_npi) != 10:
                counts["R005"] += 1
            if not claim.provider_npi.isdigit():
                counts["R006"] += 1
            if claim.provider_npi.isdigit() and len(claim.provider_npi) == 10 and claim.provider_npi not in provider_npis:
                counts["R007"] += 1

        if claim.service_from and claim.service_to and claim.service_to < claim.service_from:
            counts["R008"] += 1
        if claim.service_from and claim.service_from > run_date:
            counts["R009"] += 1

        if claim.member_id and claim.service_from:
            member = member_lookup.get(claim.member_id)
            if member and (claim.service_from < member.coverage_start or claim.service_from > member.coverage_end):
                counts["R010"] += 1

        key_to_claim_ids[claim_key(claim)].append(claim.claim_id)

    dup_participants = 0
    for claim_ids in key_to_claim_ids.values():
        if len(claim_ids) > 1:
            dup_participants += len(claim_ids)
    counts["R011"] = dup_participants

    for line in lines:
        if line.paid_cents > line.allowed_cents:
            counts["R012"] += 1
        if line.allowed_cents > line.charge_cents:
            counts["R013"] += 1
        if line.proc_code == "":
            counts["R014"] += 1
        if line.dx_code == "":
            counts["R015"] += 1

    return counts


def duplicate_key_count(claims: List[ClaimRecord]) -> int:
    key_counts = Counter(claim_key(c) for c in claims)
    return sum(1 for c in key_counts.values() if c > 1)


def stable_file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_csv(path: Path, columns: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


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
            rule_claim_ids = payload.get("claim_ids")
            if isinstance(rule_claim_ids, list):
                for claim_id in rule_claim_ids:
                    if not isinstance(claim_id, str):
                        return False
                    if claim_id and claim_id not in claim_ids:
                        return False
            participants = payload.get("participant_claim_ids")
            if isinstance(participants, list):
                for claim_id in participants:
                    if not isinstance(claim_id, str):
                        return False
                    if claim_id and claim_id not in claim_ids:
                        return False
            pairs = payload.get("source_clone_pairs")
            if isinstance(pairs, list):
                for pair in pairs:
                    if not isinstance(pair, dict):
                        return False
                    source_claim_id = pair.get("source_claim_id", "")
                    clone_claim_id = pair.get("clone_claim_id", "")
                    if source_claim_id not in claim_ids or clone_claim_id not in claim_ids:
                        return False
            refs = payload.get("line_refs")
            if isinstance(refs, list):
                for ref in refs:
                    if not isinstance(ref, dict):
                        return False
                    claim_id = ref.get("claim_id", "")
                    line_id = ref.get("line_id", "")
                    if (claim_id, line_id) not in line_refs:
                        return False
    return True


def build_dataset(seed: int, run_date: date, out_dir: Path) -> None:
    if run_date != LOCKED_RUN_DATE:
        raise AssertionError(
            f"RUN_DATE lock violation: expected {LOCKED_RUN_DATE.isoformat()}, got {run_date.isoformat()}."
        )

    rng = random.Random(seed)
    id_factory = IdFactory()
    member_factory = MemberFactory(rng)
    provider_factory = ProviderFactory()
    provider_npi_set = set(provider_factory.provider_pool)

    plans = build_batch_plan()
    if len(plans) != 60:
        raise AssertionError(f"Expected 60 batch plans, found {len(plans)}.")

    all_claim_rows: List[Dict[str, str]] = []
    all_line_rows: List[Dict[str, str]] = []
    story_rows: List[Dict[str, str]] = []
    batch_claims: Dict[str, List[ClaimRecord]] = {}
    batch_lines: Dict[str, List[LineRecord]] = {}

    manifest: Dict[str, object] = {
        "contract_id": "GCT-DS-001",
        "seed": seed,
        "run_date": run_date.isoformat(),
        "locked": {
            "run_date": LOCKED_RUN_DATE.isoformat(),
            "batch_id_format": BATCH_ID_FORMAT,
            "start_week": START_WEEK.isoformat(),
            "weeks": WEEK_COUNT,
        },
        "incidents": {},
        "batch_anomaly_guarantees": {},
    }

    w02_batch_id = ""
    w06_batch_id = ""
    w07_batch_id = ""
    w10_batch_id = ""
    w02_r007_ids: set[str] = set()

    for plan in plans:
        claims, lines_by_claim_id = generate_clean_batch(
            rng=rng,
            plan=plan,
            member_factory=member_factory,
            provider_pool=provider_factory.provider_pool,
            id_factory=id_factory,
        )

        incident_key = f"{plan.week_label}_{plan.lob}_{plan.vendor}"

        if plan.week_idx == 2 and plan.lob == "MEDICAID" and plan.vendor == "VENDOR_A":
            w02_batch_id = plan.batch_id
            w02_details = apply_w02_onboarding_blockers(claims, lines_by_claim_id, run_date)
            manifest["incidents"][incident_key] = {
                "batch_id": plan.batch_id,
                "week_start": plan.week_start.isoformat(),
                "storyline_label": plan.storyline_label,
                "rules": w02_details["rules"],
            }
            rules = manifest["incidents"][incident_key]["rules"]
            r007_claim_ids = rules["R007_NPI_NOT_FOUND"]["claim_ids"]
            w02_r007_ids = set(r007_claim_ids)

        elif plan.week_idx == 6 and plan.lob == "COMMERCIAL" and plan.vendor == "VENDOR_B":
            w06_batch_id = plan.batch_id
            w06_details = apply_w06_eligibility_incident(claims, member_factory.member_index)
            manifest["incidents"][incident_key] = {
                "batch_id": plan.batch_id,
                "week_start": plan.week_start.isoformat(),
                "storyline_label": plan.storyline_label,
                "rules": w06_details["rules"],
            }

        elif plan.week_idx == 7 and plan.lob == "COMMERCIAL" and plan.vendor == "VENDOR_C":
            w07_batch_id = plan.batch_id
            w07_details = apply_w07_duplicate_and_line_incidents(claims, lines_by_claim_id, id_factory)
            manifest["incidents"][incident_key] = {
                "batch_id": plan.batch_id,
                "week_start": plan.week_start.isoformat(),
                "storyline_label": plan.storyline_label,
                "rules": w07_details["rules"],
            }

        elif plan.week_idx == 10 and plan.lob == "MEDICAID" and plan.vendor == "VENDOR_A":
            w10_batch_id = plan.batch_id

        lines = ordered_lines_for_claims(claims, lines_by_claim_id)
        batch_claims[plan.batch_id] = claims
        batch_lines[plan.batch_id] = lines

        for claim in claims:
            all_claim_rows.append(claim.to_row())
        for line in lines:
            all_line_rows.append(line.to_row())

        story_rows.append(
            {
                "week_start": plan.week_start.isoformat(),
                "lob": plan.lob,
                "vendor": plan.vendor,
                "batch_id": plan.batch_id,
                "storyline_label": plan.storyline_label,
            }
        )

    if not (w02_batch_id and w06_batch_id and w07_batch_id and w10_batch_id):
        raise AssertionError("Failed to identify required incident batches.")

    member_rows = [m.to_row() for m in member_factory.member_rows]
    provider_rows = provider_factory.provider_rows

    checks: Dict[str, bool] = {}

    checks["topology_60_batches"] = len(batch_claims) == 60 and len(story_rows) == 60

    combo_to_batch = defaultdict(set)
    for row in story_rows:
        combo_to_batch[(row["week_start"], row["lob"], row["vendor"])].add(row["batch_id"])
    checks["topology_one_batch_per_combo"] = all(len(batch_ids) == 1 for batch_ids in combo_to_batch.values())
    checks["topology_combo_count_60"] = len(combo_to_batch) == 60

    batch_sizes = {batch_id: len(rows) for batch_id, rows in batch_claims.items()}
    checks["volume_w10_320"] = batch_sizes[w10_batch_id] == 320
    checks["volume_all_other_200"] = all(
        (size == 320 if batch_id == w10_batch_id else size == 200) for batch_id, size in batch_sizes.items()
    )

    member_lookup = member_factory.member_index
    per_batch_rule_counts: Dict[str, Dict[str, int]] = {}
    for batch_id in sorted(batch_claims.keys()):
        per_batch_rule_counts[batch_id] = evaluate_rule_counts(
            claims=batch_claims[batch_id],
            lines=batch_lines[batch_id],
            provider_npis=provider_npi_set,
            member_lookup=member_lookup,
            run_date=run_date,
        )

    w02_counts = per_batch_rule_counts[w02_batch_id]
    expected_w02 = {
        "R001": 10,
        "R002": 5,
        "R003": 10,
        "R004": 5,
        "R005": 10,
        "R006": 10,
        "R007": 10,
        "R008": 10,
        "R009": 10,
    }
    checks["w02_exact_r001_r009"] = all(w02_counts[k] == v for k, v in expected_w02.items())
    checks["w02_no_other_rules"] = all(w02_counts[f"R{i:03d}"] == 0 for i in range(10, 16))

    w06_counts = per_batch_rule_counts[w06_batch_id]
    checks["w06_exact_r010"] = w06_counts["R010"] == 6
    checks["w06_other_rules_clean"] = all(w06_counts[f"R{i:03d}"] == 0 for i in range(1, 10)) and all(
        w06_counts[f"R{i:03d}"] == 0 for i in range(11, 16)
    )

    w07_counts = per_batch_rule_counts[w07_batch_id]
    checks["w07_r011_participants_10"] = w07_counts["R011"] == 10
    checks["w07_r011_keys_5"] = duplicate_key_count(batch_claims[w07_batch_id]) == 5
    checks["w07_r012_r015_exact"] = (
        w07_counts["R012"] == 20
        and w07_counts["R013"] == 20
        and w07_counts["R014"] == 20
        and w07_counts["R015"] == 20
    )
    checks["w07_other_rules_clean"] = all(w07_counts[f"R{i:03d}"] == 0 for i in range(1, 11))

    incident_batch_ids = {w02_batch_id, w06_batch_id, w07_batch_id}
    checks["clean_weeks_outside_w02_w06_w07"] = True
    for batch_id, counts in per_batch_rule_counts.items():
        if batch_id in incident_batch_ids:
            continue
        if any(counts[f"R{i:03d}"] != 0 for i in range(1, 16)):
            checks["clean_weeks_outside_w02_w06_w07"] = False
            break

    reserved_claims = [
        c for claims in batch_claims.values() for c in claims if c.provider_npi == RESERVED_NPI_NOT_FOUND
    ]
    checks["reserved_npi_not_in_reference_providers"] = RESERVED_NPI_NOT_FOUND not in provider_npi_set
    checks["reserved_npi_only_r007_w02"] = (
        len(reserved_claims) == 10
        and all(c.batch_id == w02_batch_id for c in reserved_claims)
        and {c.claim_id for c in reserved_claims} == w02_r007_ids
    )

    # R901: W07 duplicate participation > 1%.
    r901_rate = w07_counts["R011"] / batch_sizes[w07_batch_id]
    checks["r901_dup_rate_gt_1pct"] = r901_rate > 0.01 and abs(r901_rate - 0.05) < 1e-12

    # R902: W06 eligibility mismatch 6/200 = 3%.
    r902_rate = w06_counts["R010"] / batch_sizes[w06_batch_id]
    checks["r902_elig_mismatch_gt_2pct"] = r902_rate > 0.02 and abs(r902_rate - 0.03) < 1e-12

    # R903: W10 MEDICAID/VENDOR_A count deviates >15% vs trailing 8-week median.
    medicaid_vendor_a_batch_ids = sorted(
        [batch_id for batch_id in batch_claims if "_VENDOR_A_MEDICAID_" in batch_id],
        key=lambda b: int(b.rsplit("_W", 1)[1]),
    )
    counts_mv_a = [batch_sizes[batch_id] for batch_id in medicaid_vendor_a_batch_ids]
    trailing_8 = counts_mv_a[1:9]  # W02-W09
    trailing_median = float(median(trailing_8))
    current_w10 = float(counts_mv_a[9])
    r903_deviation = abs(current_w10 - trailing_median) / trailing_median
    checks["r903_volume_shift_gt_15pct"] = r903_deviation > 0.15

    manifest["batch_anomaly_guarantees"] = {
        "R901_DUP_RATE_GT_1PCT": {
            "batch_id": w07_batch_id,
            "claims_in_batch": batch_sizes[w07_batch_id],
            "duplicate_participating_claims": w07_counts["R011"],
            "rate": r901_rate,
        },
        "R902_ELIG_MISMATCH_GT_2PCT": {
            "batch_id": w06_batch_id,
            "claims_in_batch": batch_sizes[w06_batch_id],
            "eligibility_mismatch_claims": w06_counts["R010"],
            "rate": r902_rate,
        },
        "R903_VOLUME_SHIFT_GT_15PCT": {
            "batch_id": w10_batch_id,
            "claims_in_batch": batch_sizes[w10_batch_id],
            "trailing_8_week_median": trailing_median,
            "deviation_rate": r903_deviation,
            "basis": "COUNT(*) encounters_header rows per batch_id",
        },
    }

    data_raw_dir = out_dir / "data_raw"
    outputs_dir = out_dir / "outputs"
    write_csv(data_raw_dir / "encounters_header.csv", HEADER_COLUMNS, all_claim_rows)
    write_csv(data_raw_dir / "encounters_lines.csv", LINES_COLUMNS, all_line_rows)
    write_csv(data_raw_dir / "reference_members.csv", MEMBERS_COLUMNS, member_rows)
    write_csv(data_raw_dir / "reference_providers.csv", PROVIDERS_COLUMNS, provider_rows)
    write_csv(outputs_dir / "story_map.csv", STORY_COLUMNS, story_rows)

    # Manifest reference integrity check (claim_ids/line_ids only point at existing rows).
    all_claim_ids = {row["claim_id"] for row in all_claim_rows if row["claim_id"]}
    all_line_ref_pairs = {(row["claim_id"], row["line_id"]) for row in all_line_rows}
    checks["manifest_references_exist"] = ensure_manifest_references_exist(
        manifest=manifest,
        claim_ids=all_claim_ids,
        line_refs=all_line_ref_pairs,
    )

    failed = sorted([name for name, passed in checks.items() if not passed])
    if failed:
        raise AssertionError("Acceptance checks failed: " + ", ".join(failed))

    manifest_path = outputs_dir / "injection_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    digest_paths = {
        "data_raw/encounters_header.csv": data_raw_dir / "encounters_header.csv",
        "data_raw/encounters_lines.csv": data_raw_dir / "encounters_lines.csv",
        "data_raw/reference_members.csv": data_raw_dir / "reference_members.csv",
        "data_raw/reference_providers.csv": data_raw_dir / "reference_providers.csv",
        "outputs/injection_manifest.json": manifest_path,
        "outputs/story_map.csv": outputs_dir / "story_map.csv",
    }
    digests = {name: stable_file_digest(path) for name, path in digest_paths.items()}

    receipt_lines: List[str] = [
        "# Dataset Receipt - GCT-DS-001",
        "",
        f"- seed: {seed}",
        f"- run_date: {run_date.isoformat()}",
        f"- start_week: {START_WEEK.isoformat()}",
        f"- total_batches: {len(batch_claims)}",
        f"- total_claims: {len(all_claim_rows)}",
        f"- total_lines: {len(all_line_rows)}",
        f"- total_members: {len(member_rows)}",
        f"- total_providers: {len(provider_rows)}",
        f"- locked_batch_id_format: {BATCH_ID_FORMAT}",
        "",
        "## Incident Batches",
        f"- W02 MEDICAID/VENDOR_A: {w02_batch_id}",
        f"- W06 COMMERCIAL/VENDOR_B: {w06_batch_id}",
        f"- W07 COMMERCIAL/VENDOR_C: {w07_batch_id}",
        f"- W10 MEDICAID/VENDOR_A: {w10_batch_id}",
        "",
        "## Acceptance Checks",
    ]
    for key in sorted(checks.keys()):
        receipt_lines.append(f"- {'PASS' if checks[key] else 'FAIL'} {key}")

    receipt_lines.extend(
        [
            "",
            "## Batch Anomaly Guarantees",
            f"- R901 dup participation: {w07_counts['R011']}/{batch_sizes[w07_batch_id]} = {r901_rate:.4f}",
            f"- R902 elig mismatch: {w06_counts['R010']}/{batch_sizes[w06_batch_id]} = {r902_rate:.4f}",
            (
                "- R903 volume shift: "
                f"{int(current_w10)}/{int(trailing_median)} median baseline, deviation={r903_deviation:.4f}"
            ),
            "",
            "## Determinism Fingerprints (sha256)",
        ]
    )
    for name in sorted(digests.keys()):
        receipt_lines.append(f"- {name}: {digests[name]}")

    receipt_path = outputs_dir / "dataset_receipt.md"
    receipt_path.write_text("\n".join(receipt_lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date)
    out_dir = Path(args.out_dir).resolve()
    build_dataset(seed=args.seed, run_date=run_date, out_dir=out_dir)


if __name__ == "__main__":
    main()
