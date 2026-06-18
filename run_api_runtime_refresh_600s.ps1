$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
$IntervalSeconds = 600
Set-Location $ProjectRoot

Write-Host "Starting API runtime refresh loop every $IntervalSeconds seconds..." -ForegroundColor Cyan
Write-Host "This loop runs: data_collector.py -> admin_api_enrichment.py -> alert_rules_engine.py -> intelligence_rules_engine.py -> wait 600s" -ForegroundColor Yellow
Write-Host "Open a SECOND PowerShell for: python web.py" -ForegroundColor Green

while ($true) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    Write-Host "[$stamp] Running Jira/API collector..." -ForegroundColor Cyan
    python .\data_collector.py
    if ($LASTEXITCODE -ne 0) { Start-Sleep -Seconds $IntervalSeconds; continue }

    Write-Host "[$stamp] Running Admin API enrichment..." -ForegroundColor Cyan
    python .\admin_api_enrichment.py
    if ($LASTEXITCODE -ne 0) { Start-Sleep -Seconds $IntervalSeconds; continue }

    Write-Host "[$stamp] Applying alert rules..." -ForegroundColor Cyan
    python .\alert_rules_engine.py
    if ($LASTEXITCODE -ne 0) { Start-Sleep -Seconds $IntervalSeconds; continue }

    Write-Host "[$stamp] Applying intelligence rules..." -ForegroundColor Cyan
    python .\intelligence_rules_engine.py
    if ($LASTEXITCODE -ne 0) { Start-Sleep -Seconds $IntervalSeconds; continue }

    Write-Host "[$stamp] Cycle complete. Next refresh in $IntervalSeconds seconds." -ForegroundColor Green
    Start-Sleep -Seconds $IntervalSeconds
}
