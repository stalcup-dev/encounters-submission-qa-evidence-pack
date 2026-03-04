# AUDIT Receipt (GCT-AUD-006)

Generated (UTC): `2026-03-03T18:29:31+00:00`

## Quick Start Command Chain
```powershell
.\.venv\Scripts\Activate.ps1
python src/generate_dataset.py --seed 42 --run_date 2026-05-10 --out_dir .
python src/verify_dataset.py --run_date 2026-05-10
python src/verify_outputs.py
python src/verify_report_html.py
python src/verify_no_absolute_paths.py
python src/build_kpi_snapshot.py
powershell -ExecutionPolicy Bypass -File scripts/export_reports.ps1 -SkipPdf
```

## Verifier Status
| Check | Result | Summary |
|---|---|---|
| `src/verify_dataset.py --run_date 2026-05-10` | PASS | `SUMMARY: PASS=40 FAIL=0 SKIP=1 TOTAL=41` |
| `src/verify_outputs.py` | PASS | `SUMMARY: 15/15 checks passed, 0 failed` |
| `src/verify_report_html.py` | PASS | `PASS: HTML verification passed for docs/Encounters_QA_Report.html` |
| `src/verify_no_absolute_paths.py` | PASS | `PASS: no forbidden absolute paths found in 14 docs files` |

## KPI Snapshot
- [docs/kpi_snapshot.md](kpi_snapshot.md)

## Export Step
- HTML export command:
  - `powershell -ExecutionPolicy Bypass -File scripts/export_reports.ps1 -SkipPdf`
- HTML outputs:
  - `docs/Encounters_QA_Report.html`
  - `docs/UAT_Evidence_Pack.html`
- PDF note:
  - Manual Print-to-PDF fallback is acceptable from exported HTML files.

