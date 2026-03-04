from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CheckResult:
    command: str
    passed: bool
    summary: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate docs/AUDIT_RECEIPT.md with portable paths.")
    parser.add_argument("--run_date", default="2026-05-10", help="Run date passed to verify_dataset.py.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Project root path.")
    return parser.parse_args()


def run_check(root: Path, command: str) -> CheckResult:
    proc = subprocess.run(
        [sys.executable, *command.split()],
        cwd=root,
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "").strip()
    if proc.stderr:
        output = (output + "\n" + proc.stderr.strip()).strip()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary = lines[-1] if lines else ("PASS" if proc.returncode == 0 else "FAIL")
    return CheckResult(command=command, passed=proc.returncode == 0, summary=summary)


def build_receipt_text(run_date: str, results: list[CheckResult]) -> str:
    status_by_cmd = {r.command: r for r in results}
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    quick_start = [
        f"python src/generate_dataset.py --seed 42 --run_date {run_date} --out_dir .",
        f"python src/verify_dataset.py --run_date {run_date}",
        "python src/verify_outputs.py",
        "python src/verify_report_html.py",
        "python src/verify_no_absolute_paths.py",
        "python src/build_kpi_snapshot.py",
        "powershell -ExecutionPolicy Bypass -File scripts/export_reports.ps1 -SkipPdf",
    ]

    verification_commands = [
        f"src/verify_dataset.py --run_date {run_date}",
        "src/verify_outputs.py",
        "src/verify_report_html.py",
        "src/verify_no_absolute_paths.py",
    ]

    lines: list[str] = []
    lines.append("# AUDIT Receipt (GCT-AUD-006)")
    lines.append("")
    lines.append(f"Generated (UTC): `{generated}`")
    lines.append("")
    lines.append("## Quick Start Command Chain")
    lines.append("```powershell")
    lines.append(".\\.venv\\Scripts\\Activate.ps1")
    for cmd in quick_start:
        lines.append(cmd)
    lines.append("```")
    lines.append("")
    lines.append("## Verifier Status")
    lines.append("| Check | Result | Summary |")
    lines.append("|---|---|---|")
    for cmd in verification_commands:
        result = status_by_cmd.get(cmd)
        if result is None:
            lines.append(f"| `{cmd}` | FAIL | not executed |")
            continue
        verdict = "PASS" if result.passed else "FAIL"
        lines.append(f"| `{cmd}` | {verdict} | `{result.summary}` |")
    lines.append("")
    lines.append("## KPI Snapshot")
    lines.append("- [docs/kpi_snapshot.md](kpi_snapshot.md)")
    lines.append("")
    lines.append("## Export Step")
    lines.append("- HTML export command:")
    lines.append("  - `powershell -ExecutionPolicy Bypass -File scripts/export_reports.ps1 -SkipPdf`")
    lines.append("- HTML outputs:")
    lines.append("  - `docs/Encounters_QA_Report.html`")
    lines.append("  - `docs/UAT_Evidence_Pack.html`")
    lines.append("- PDF note:")
    lines.append("  - Manual Print-to-PDF fallback is acceptable from exported HTML files.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_path = root / "docs" / "AUDIT_RECEIPT.md"

    checks = [
        f"src/verify_dataset.py --run_date {args.run_date}",
        "src/verify_outputs.py",
        "src/verify_report_html.py",
        "src/verify_no_absolute_paths.py",
    ]

    results = [run_check(root, command) for command in checks]
    text = build_receipt_text(args.run_date, results)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote audit receipt: {out_path}")

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
