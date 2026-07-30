# JOM_BACKEND_STATIC_TRUTH_REMEDIATION_V1
# Legacy/static truth references in this file have been neutralised.
# This script must not silently read legacy snapshots as website/backend truth.
# Unavailable live/runtime data must be reported as unavailable.
$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

Write-Host "Previewing static-data cleanup candidates (no deletes performed)..." -ForegroundColor Cyan

$patterns = @(
    'export-users*.csv',
    '*managed_accounts*.csv',
    '*.csv'
)

Get-ChildItem -Path $ProjectRoot -File -Filter '*.csv' | Select-Object FullName, Length, LastWriteTime
Write-Host "" 
Write-Host "Suggested manual review targets:" -ForegroundColor Yellow
Write-Host "- top-level CSV exports"
Write-Host "- obsolete latest_run_safe_partial.json only after runtime_contract_unavailable_latest_run_json and runtime_contract_unavailable_latest_run_admin_enriched_json are proven healthy"
Write-Host "- duplicate UI/pack zip files only after you confirm they are already archived elsewhere"
