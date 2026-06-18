$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

Write-Host "Applying alert rules once..." -ForegroundColor Cyan
python .\alert_rules_engine.py
if ($LASTEXITCODE -ne 0) { throw "alert_rules_engine.py failed" }
Write-Host "Now run python web.py and check /api/data or the runtime widget." -ForegroundColor Green
