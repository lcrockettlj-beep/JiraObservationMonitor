$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

Write-Host "Applying intelligence rules once..." -ForegroundColor Cyan
python .\intelligence_rules_engine.py
if ($LASTEXITCODE -ne 0) { throw "intelligence_rules_engine.py failed" }
Write-Host "Now run python web.py and review the intelligence cards/watchlist." -ForegroundColor Green
