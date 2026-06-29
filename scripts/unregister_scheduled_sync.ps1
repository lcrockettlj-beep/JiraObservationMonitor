# ============================================================
# JOM_Sync_Runtime — Scheduled Task Unregistration
# ============================================================
# Removes the Windows Task Scheduler task used to run
# the JOM sync runtime.
# ============================================================

$TaskName = "JOM_Sync_Runtime"

Write-Host "Checking scheduled task: $TaskName" -ForegroundColor Cyan

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if (-not $existing) {
    Write-Host "No scheduled task found for: $TaskName" -ForegroundColor Yellow
    exit 0
}

Write-Host "Scheduled task found. Removing: $TaskName" -ForegroundColor Yellow

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "Scheduled task removed successfully." -ForegroundColor Green