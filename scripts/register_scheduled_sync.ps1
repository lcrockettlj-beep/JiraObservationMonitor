param(
    [string]$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor",
    [string]$TaskName = "JOM_Sync_Runtime",
    [int]$IntervalMinutes = 60
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ProjectRoot)) { throw "Project root not found: $ProjectRoot" }
$Python = (Get-Command python -ErrorAction Stop).Source
$Script = Join-Path $ProjectRoot "scripts\run_operational_snapshot.py"
if (-not (Test-Path $Script)) { throw "Operational snapshot script not found: $Script" }

$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "JOM Operational Snapshot - runs run_operational_snapshot.py every $IntervalMinutes minutes" | Out-Null
Write-Host "Registered $TaskName -> $Script every $IntervalMinutes minutes" -ForegroundColor Green
