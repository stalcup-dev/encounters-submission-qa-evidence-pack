# Repo Map

This file is the quick navigation index for repository structure.

## Top-Level Folders

| Path | What lives here |
|---|---|
| `docs/` | Human-readable artifacts: HTML reports, runbook, UAT plan/evidence, KPI snapshot, metric definitions, and release records. |
| `notebooks/` | Execution notebooks: `01_validate.ipynb`, `02_analysis.ipynb`, `03_uat.ipynb`. |
| `outputs/` | Generated operational outputs, screenshots, and UAT run folders under `outputs/uat/`. |
| `data_raw/` | Synthetic input datasets and reference tables used for generation/validation. |
| `src/` | Python generators, verifiers, and report support scripts. |
| `scripts/` | PowerShell automation for release gating and report export. |

## Key Entry Points

- Start page: `README.md`
- Hiring manager quick path: `docs/START_HERE.md`
- Source-of-truth contract: `SOURCE_OF_TRUTH_Encounters_QA_Lab.md`
- End-to-end release gate: `scripts/release_gate.ps1`

## Core Artifacts

- Main report: `docs/Encounters_QA_Report.html`
- UAT evidence: `docs/UAT_Evidence_Pack.html`
- KPI snapshot: `docs/kpi_snapshot.md`
- Audit receipt: `docs/AUDIT_RECEIPT.md`
