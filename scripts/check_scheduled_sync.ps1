# ============================================================
# JOM_Sync_Runtime - Scheduled Task Status Check
# ============================================================
# Shows current state of the scheduled task and the last
# entries from the sync log file. ASCII only - no Unicode.
# ============================================================

$TaskName    = "JOM_Sync_Runtime"
$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
$LogFile     = Join-Path $ProjectRoot "docs\control\logs\scheduled_sync.log"

Write-Host "JOM Scheduled Sync Status" -ForegroundColor Cyan
Write-Host "========================="
Write-Host ""

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if (-not $task) {
    Write-Host "[NOT REGISTERED] Task '$TaskName' is not registered" -ForegroundColor Red
    Write-Host ""
    Write-Host "To register the task:"
    Write-Host "   .\scripts\register_scheduled_sync.ps1"
    exit 0
}

$info = Get-ScheduledTaskInfo -TaskName $TaskName

Write-Host "Task Information" -ForegroundColor Green
Write-Host "   Name:         $($task.TaskName)"
Write-Host "   State:        $($task.State)"
Write-Host "   Last Run:     $($info.LastRunTime)"
Write-Host "   Last Result:  $($info.LastTaskResult)"
Write-Host "   Next Run:     $($info.NextRunTime)"
Write-Host "   Missed Runs:  $($info.NumberOfMissedRuns)"
Write-Host ""

$resultCode = $info.LastTaskResult
switch ($resultCode) {
    0           { Write-Host "[OK] Last run: SUCCESS" -ForegroundColor Green }
    267009      { Write-Host "[RUNNING] Last run: Currently running" -ForegroundColor Yellow }
    267011      { Write-Host "[PENDING] Last run: Has not yet run" -ForegroundColor Cyan }
    255         { Write-Host "[WARN] Last run: Wrapper exited 255 - check log for actual sync result" -ForegroundColor Yellow }
    default     { Write-Host "[?] Last run: Code $resultCode" -ForegroundColor Yellow }
}

Write-Host ""

if (Test-Path $LogFile) {
    Write-Host "Last 20 lines of sync log:" -ForegroundColor Cyan
    Write-Host "--------------------------"
    Get-Content $LogFile -Encoding UTF8 -Tail 20
} else {
    Write-Host "No log file yet - task may not have run." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Useful commands:"
Write-Host "   Force run now:    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "   View in GUI:      taskschd.msc"
Write-Host "   Stop task:        Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "   Remove task:      .\scripts\unregister_scheduled_sync.ps1"
Write-Host "   View log clean:   .\scripts\view_sync_log.ps1"