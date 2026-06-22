param(
    [string]$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

Write-Host "=== Repairing estate page ===" -ForegroundColor Cyan

if (Test-Path "templates\estate.html.bak") {
    Copy-Item "templates\estate.html.bak" "templates\estate.html" -Force
    Write-Host "Restored templates\estate.html from backup" -ForegroundColor Green
} else {
    throw "Backup file templates\estate.html.bak was not found."
}

Write-Host "`nRun these verification commands next:" -ForegroundColor Yellow
Write-Host "Invoke-WebRequest http://127.0.0.1:5000/estate -TimeoutSec 5 -UseBasicParsing | Select-Object StatusCode"
Write-Host "Invoke-RestMethod http://127.0.0.1:5000/api/source-state -TimeoutSec 5 | Select-Object source_mode, auto_sync_active"
