# ============================================================
# JOM_Sync_Runtime — Scheduled Task Registration
# ============================================================
# Registers a Windows Task Scheduler task that runs the
# sync_runtime.py orchestrator every 10 minutes via a
# batch wrapper that handles logging.
# ============================================================

$TaskName    = "JOM_Sync_Runtime"
$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
$Wrapper     = Join-Path $ProjectRoot "scripts\run_sync_for_scheduler.cmd"
$LogDir      = Join-Path $ProjectRoot "docs\control\logs"

Write-Host "Registering scheduled task: $TaskName" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"
Write-Host "Wrapper:      $Wrapper"
Write-Host "Log dir:      $LogDir"
Write-Host ""

if (-not (Test-Path $LogDir)) {
    New-Item -Path $LogDir -ItemType Directory -Force | Out-Null
}

if (-not (Test-Path $Wrapper)) {
    Write-Host "ERROR: Wrapper not found at $Wrapper" -ForegroundColor Red
    Write-Host "Create scripts\run_sync_for_scheduler.cmd first."
    exit 1
}

# Action — just run the wrapper
$Action = New-ScheduledTaskAction -Execute $Wrapper

# Trigger — every 10 minutes starting now, runs indefinitely
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 10)

# Settings — interactive only, skip if running, time-limit hung runs
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

# Principal — current user, interactive logon
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

# Remove existing version of the task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Existing task found - removing first..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Register
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "JOM Sync Runtime - runs sync_runtime.py every 10 minutes" | Out-Null

Write-Host ""
Write-Host "Task registered successfully" -ForegroundColor Green
Write-Host ""
Write-Host "Details:"
Write-Host "   Name:       $TaskName"
Write-Host "   Runs every: 10 minutes"
Write-Host "   Runs as:    $env:USERDOMAIN\$env:USERNAME"
Write-Host "   Wrapper:    $Wrapper"
Write-Host "   Log dir:    $LogDir"
Write-Host ""
Write-Host "To check status: .\scripts\check_scheduled_sync.ps1"
Write-Host "To remove task:  .\scripts\unregister_scheduled_sync.ps1"
Write-Host ""
Write-Host "First run happens within 10 minutes."
Write-Host "Force immediate run: Start-ScheduledTask -TaskName '$TaskName'"