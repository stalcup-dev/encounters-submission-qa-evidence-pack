from __future__ import annotations

import html as html_lib
import re
from pathlib import Path

REQUIRED_STRINGS = [
    "Code Legend (Batch Flags)",
    "How to interpret this report",
    "Context & Scope",
    "Metric Definitions",
    "W06 incident: eligibility + R902",
    "W07 incident: duplicates + R901 + monitors",
    "W10 incident: volume + R903 only",
]

LEGACY_STRINGS = [
    "what_changed_next",
    "what changed next",
    "2,526",
    "BLOCKER=2,387",
]

STORYBOARD_HEADER = "Storyboard (10-week timeline)"
STORYBOARD_NEXT_STEP_HEADERS = [
    "next_week_delta",
    "next_week_label",
    "what changed next",
    "what_changed_next",
]
STORYBOARD_TRUNCATION_MARKERS = ["...", "\u2026", "&hellip;", "&#8230;"]


def extract_storyboard_section(raw_html: str) -> str:
    start = raw_html.find('<h2 id="Storyboard-(10-week-timeline)">')
    if start < 0:
        return ""
    next_h2 = raw_html.find("<h2 id=", start + 1)
    if next_h2 < 0:
        return raw_html[start:]
    return raw_html[start:next_h2]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report_path = root / "docs" / "Encounters_QA_Report.html"

    if not report_path.exists():
        print(f"FAIL: report not found at {report_path}")
        return 1

    html = report_path.read_text(encoding="utf-8", errors="replace")
    rendered_text = html_lib.unescape(html)
    rendered_text_lower = rendered_text.lower()

    failures: list[str] = []

    for needle in REQUIRED_STRINGS:
        if needle not in rendered_text:
            failures.append(f"missing required string: {needle!r}")

    for needle in LEGACY_STRINGS:
        if needle.lower() in rendered_text_lower:
            failures.append(f"found forbidden legacy string: {needle!r}")

    storyboard_raw = extract_storyboard_section(html)
    if not storyboard_raw:
        failures.append("missing storyboard section: 'Storyboard (10-week timeline)'")
    else:
        storyboard_text = html_lib.unescape(storyboard_raw)
        storyboard_text_lower = storyboard_text.lower()

        if STORYBOARD_HEADER not in storyboard_text:
            failures.append(f"missing storyboard header text: {STORYBOARD_HEADER!r}")

        if not any(h.lower() in storyboard_text_lower for h in STORYBOARD_NEXT_STEP_HEADERS):
            failures.append(
                "missing storyboard next-step column header (expected one of: "
                + ", ".join(repr(h) for h in STORYBOARD_NEXT_STEP_HEADERS)
                + ")"
            )

        for marker in STORYBOARD_TRUNCATION_MARKERS:
            # Match literal marker in rendered/raw section text.
            if marker in storyboard_text or marker in storyboard_raw:
                failures.append(
                    "storyboard appears truncated: found ellipsis marker "
                    f"{marker!r} in storyboard section"
                )
                break

        # Extra hard check: no table cell that is exactly "...".
        if re.search(r"<td>\s*\.{3}\s*</td>", storyboard_raw, flags=re.IGNORECASE):
            failures.append("storyboard contains a truncated table cell '<td>...</td>'")

    if failures:
        print("FAIL: HTML verification failed for docs/Encounters_QA_Report.html")
        for item in failures:
            print(f"- {item}")
        return 1

    print("PASS: HTML verification passed for docs/Encounters_QA_Report.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
