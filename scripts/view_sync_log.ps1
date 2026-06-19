# JOM Sync Log Viewer — handles UTF-8 properly
$LogFile = "C:\Users\Luke_C\Desktop\JiraObservationMonitor\docs\control\logs\scheduled_sync.log"

if (-not (Test-Path $LogFile)) {
    Write-Host "No log file yet at $LogFile" -ForegroundColor Yellow
    exit 0
}

$lines = if ($args.Count -gt 0) { [int]$args[0] } else { 50 }

Write-Host "JOM Sync Log (last $lines lines)" -ForegroundColor Cyan
Write-Host "================================="
Get-Content $LogFile -Encoding UTF8 -Tail $lines