param(
    [switch]$SkipPdf
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DocsDir = Join-Path $ProjectRoot "docs"
$NotebookDir = Join-Path $ProjectRoot "notebooks"
$PythonExe = Join-Path $ProjectRoot ".venv\\Scripts\\python.exe"

if (-not (Test-Path $DocsDir)) {
    New-Item -ItemType Directory -Path $DocsDir | Out-Null
}

if (-not (Test-Path $PythonExe)) {
    throw "Expected virtualenv python at $PythonExe. Create/install .venv first."
}

function Invoke-NbConvert {
    param(
        [Parameter(Mandatory = $true)][string]$NotebookPath,
        [Parameter(Mandatory = $true)][string]$To,
        [Parameter(Mandatory = $true)][string]$OutputName
    )

    & $PythonExe -m jupyter nbconvert `
        $NotebookPath `
        --to $To `
        --no-input `
        --output $OutputName `
        --output-dir $DocsDir

    if ($LASTEXITCODE -ne 0) {
        throw "nbconvert failed for '$NotebookPath' (to=$To, output=$OutputName) with exit code $LASTEXITCODE."
    }
}

Write-Host "Exporting HTML reports (code hidden)..."
Invoke-NbConvert -NotebookPath (Join-Path $NotebookDir "02_analysis.ipynb") -To "html" -OutputName "Encounters_QA_Report.html"
Invoke-NbConvert -NotebookPath (Join-Path $NotebookDir "03_uat.ipynb") -To "html" -OutputName "UAT_Evidence_Pack.html"
Write-Host "HTML exports complete:"
Write-Host " - docs/Encounters_QA_Report.html"
Write-Host " - docs/UAT_Evidence_Pack.html"

if ($SkipPdf) {
    Write-Host "Skipping PDF export because -SkipPdf was passed."
    exit 0
}

Write-Host "Attempting PDF exports (code hidden)..."
$pdfFailures = @()

try {
    Invoke-NbConvert -NotebookPath (Join-Path $NotebookDir "02_analysis.ipynb") -To "pdf" -OutputName "Encounters_QA_Report.pdf"
}
catch {
    $pdfFailures += "Encounters_QA_Report.pdf"
    Write-Warning "PDF export failed for Encounters_QA_Report.pdf. Likely missing LaTeX/pandoc. $_"
}

try {
    Invoke-NbConvert -NotebookPath (Join-Path $NotebookDir "03_uat.ipynb") -To "pdf" -OutputName "UAT_Evidence_Pack.pdf"
}
catch {
    $pdfFailures += "UAT_Evidence_Pack.pdf"
    Write-Warning "PDF export failed for UAT_Evidence_Pack.pdf. Likely missing LaTeX/pandoc. $_"
}

if ($pdfFailures.Count -gt 0) {
    Write-Host ""
    Write-Host "PDF exports were not fully generated. Use README print-to-PDF fallback steps."
    Write-Host "Failed targets: $($pdfFailures -join ', ')"
    exit 0
}

Write-Host "PDF exports complete:"
Write-Host " - docs/Encounters_QA_Report.pdf"
Write-Host " - docs/UAT_Evidence_Pack.pdf"
