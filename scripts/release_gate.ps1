param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$activate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Write-Error "Missing virtual environment activation script: .venv\Scripts\Activate.ps1"
    exit 1
}

. $activate

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Host ""
    Write-Host "[$Name]"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Step failed: $Name (exit code $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
}

Invoke-Step -Name "1/8 Generate dataset" -Action {
    python src/generate_dataset.py --seed 42 --run_date 2026-05-10 --out_dir .
}

Invoke-Step -Name "2/8 Verify dataset" -Action {
    python src/verify_dataset.py --run_date 2026-05-10
}

Invoke-Step -Name "3/8 Verify outputs" -Action {
    python src/verify_outputs.py
}

Invoke-Step -Name "4/8 Verify report HTML" -Action {
    python src/verify_report_html.py
}

Invoke-Step -Name "5/8 Verify no absolute paths" -Action {
    python src/verify_no_absolute_paths.py
}

Invoke-Step -Name "6/8 Build KPI snapshot" -Action {
    python src/build_kpi_snapshot.py
}

Invoke-Step -Name "7/8 Export HTML reports" -Action {
    powershell -ExecutionPolicy Bypass -File scripts/export_reports.ps1 -SkipPdf
}

Invoke-Step -Name "8/8 Build audit receipt" -Action {
    python src/build_audit_receipt.py
}

Write-Host ""
Write-Host "PASS: release gate completed."
Write-Host "Outputs:"
Write-Host " - docs/Encounters_QA_Report.html"
Write-Host " - docs/UAT_Evidence_Pack.html"
Write-Host " - docs/kpi_snapshot.md"
Write-Host " - docs/AUDIT_RECEIPT.md"
exit 0
