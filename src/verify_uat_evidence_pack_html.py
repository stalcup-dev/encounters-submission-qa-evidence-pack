from __future__ import annotations

from pathlib import Path

FORBIDDEN_STRINGS = [
    "C:\\",
    "/Users/",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report_path = root / "docs" / "UAT_Evidence_Pack.html"

    if not report_path.exists():
        print(f"FAIL: report not found at {report_path}")
        return 1

    html = report_path.read_text(encoding="utf-8", errors="replace")

    failures: list[str] = []
    for needle in FORBIDDEN_STRINGS:
        if needle in html:
            failures.append(f"found forbidden absolute-path fragment: {needle!r}")

    if failures:
        print("FAIL: UAT evidence pack HTML contains absolute local paths")
        for item in failures:
            print(f"- {item}")
        return 1

    print("PASS: UAT evidence pack HTML contains no forbidden absolute local paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
