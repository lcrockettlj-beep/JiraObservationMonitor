# ============================================================
# JOM_Sync_Runtime — Scheduled Task Removal
# ============================================================
# Safely removes the JOM scheduled task.
# Does NOT delete logs or any project files.
# ============================================================

$TaskName = "JOM_Sync_Runtime"

Write-Host "🗑️  Removing scheduled task: $TaskName" -ForegroundColor Cyan

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if (-not $existing) {
    Write-Host "ℹ️  Task '$TaskName' does not exist. Nothing to remove." -ForegroundColor Yellow
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "✅ Task '$TaskName' removed successfully" -ForegroundColor Green
Write-Host ""
Write-Host "ℹ️  Sync workflow can still be run manually:"
Write-Host "   python scripts\sync_runtime.py"