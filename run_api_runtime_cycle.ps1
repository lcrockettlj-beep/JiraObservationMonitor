$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

Write-Host "Running Jira/API collector..." -ForegroundColor Cyan
python .\data_collector.py
if ($LASTEXITCODE -ne 0) { throw "data_collector.py failed" }

Write-Host "Running Admin API enrichment..." -ForegroundColor Cyan
python .\admin_api_enrichment.py
if ($LASTEXITCODE -ne 0) { throw "admin_api_enrichment.py failed" }

Write-Host "Current runtime source state check recommended:" -ForegroundColor Green
Write-Host "  http://127.0.0.1:5000/api/source-state" -ForegroundColor Yellow
Write-Host "To start the site manually, run:" -ForegroundColor Green
Write-Host "  python web.py" -ForegroundColor Yellow
