from __future__ import annotations

from pathlib import Path

FORBIDDEN_FRAGMENTS = [
    "C:\\",
    "/Users/",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    docs_dir = root / "docs"
    targets = sorted(list(docs_dir.glob("*.md")) + list(docs_dir.glob("*.html")))

    if not targets:
        print(f"FAIL: no docs files found under {docs_dir}")
        return 1

    failures: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for needle in FORBIDDEN_FRAGMENTS:
                if needle in line:
                    failures.append(f"{path.relative_to(root)}:{line_no} contains {needle!r}")

    if failures:
        print("FAIL: absolute machine-specific paths found in docs/*.md or docs/*.html")
        for item in failures:
            print(f"- {item}")
        return 1

    print(f"PASS: no forbidden absolute paths found in {len(targets)} docs files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
