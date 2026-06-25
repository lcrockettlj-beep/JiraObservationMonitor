param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host "[Morning Pipeline] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "[OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

cd $ProjectRoot

Write-Step "Starting morning pipeline"

# 1. Run collector
Write-Step "Running data collection"
python data_collector.py

if ($LASTEXITCODE -ne 0) {
    Write-Warn "Data collector failed — aborting pipeline"
    exit 1
}

Write-Ok "Data collection complete"

# 2. Validate runtime presence
Write-Step "Validating runtime presence"
$runtimeFile = ".\backups\latest_runtime\current\latest_run.json"

if (-not (Test-Path $runtimeFile)) {
    Write-Warn "Runtime file not found"
    exit 1
}

$runtime = Get-Content $runtimeFile | ConvertFrom-Json
Write-Host "Runtime timestamp: $($runtime.run_timestamp_local)"

Write-Ok "Runtime present"

# 3. Run sync
Write-Step "Running sync pipeline"
python scripts\sync_runtime.py

if ($LASTEXITCODE -ne 0) {
    Write-Warn "Sync failed — aborting"
    exit 1
}

Write-Ok "Sync complete"

# 4. Run snapshot controller / anchor self-heal
Write-Step "Running snapshot controller"
python .\scripts\snapshot_controller.py

if ($LASTEXITCODE -ne 0) {
    Write-Warn "Snapshot controller failed or returned warning state"
}

# 5. Check anchor
Write-Step "Waiting briefly for anchor creation"
Start-Sleep -Seconds 10

Write-Step "Checking for today's anchor"
$today = Get-Date -Format "yyyy-MM-dd"
$anchor = Get-ChildItem ".\snapshots\*anchor_morning*" | Where-Object { $_.Name -like "*$today*" }

if ($anchor) {
    Write-Ok "Morning anchor detected: $($anchor.Name)"
} else {
    Write-Warn "No morning anchor found yet after wait"
}

Write-Step "Morning pipeline complete"


