# ============================================================
# health_check.ps1 - JOM Quick Smoke Test
# ============================================================
#
# Runs 14 health checks across the full JOM platform.
# Designed to run in under 30 seconds and give clear pass/fail
# results for each layer of the system.
#
# Usage:
#   .\scripts\health_check.ps1
#
# Or for executable bypass if needed:
#   powershell -ExecutionPolicy Bypass -File .\scripts\health_check.ps1
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed
# ============================================================

$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
Set-Location $ProjectRoot

$ErrorActionPreference = "Continue"
$Total = 14
$Passed = 0
$Failed = 0
$Warnings = 0

function Write-Banner {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ("=" * 65) -ForegroundColor Cyan
    Write-Host ""
}

function Test-Result {
    param(
        [int]$Number,
        [string]$Label,
        [bool]$Success,
        [string]$Message,
        [string]$Suggestion = ""
    )
    $padLabel = $Label.PadRight(34, ".")
    $prefix = "[$Number/$($script:Total)] $padLabel"
    if ($Success) {
        Write-Host "$prefix " -NoNewline
        Write-Host "PASS " -NoNewline -ForegroundColor Green
        Write-Host $Message
        $script:Passed++
    } else {
        Write-Host "$prefix " -NoNewline
        Write-Host "FAIL " -NoNewline -ForegroundColor Red
        Write-Host $Message
        if ($Suggestion) {
            Write-Host "       -> $Suggestion" -ForegroundColor Yellow
        }
        $script:Failed++
    }
}

function Test-Warning {
    param(
        [int]$Number,
        [string]$Label,
        [string]$Message,
        [string]$Suggestion = ""
    )
    $padLabel = $Label.PadRight(34, ".")
    $prefix = "[$Number/$($script:Total)] $padLabel"
    Write-Host "$prefix " -NoNewline
    Write-Host "WARN " -NoNewline -ForegroundColor Yellow
    Write-Host $Message
    if ($Suggestion) {
        Write-Host "       -> $Suggestion" -ForegroundColor Yellow
    }
    $script:Warnings++
    $script:Passed++
}

function Get-BackupManifestSummary {
    param([string]$Root)

    $manifestPath = Join-Path $Root "backups\latest_runtime\latest_manifest.json"
    if (-not (Test-Path $manifestPath)) {
        return $null
    }

    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    }
    catch {
        return [PSCustomObject]@{
            path = $manifestPath
            exists = $true
            parse_ok = $false
            error = $_.Exception.Message
        }
    }

    $created = $null
    $ageSeconds = $null
    try {
        $created = [datetime]::Parse($manifest.created_at_local)
        $ageSeconds = [math]::Round(((Get-Date) - $created).TotalSeconds, 0)
    }
    catch {}

    return [PSCustomObject]@{
        path = $manifestPath
        exists = $true
        parse_ok = $true
        created_at_local = $manifest.created_at_local
        age_seconds = $ageSeconds
        copied_count = [int]($manifest.copied_count)
        missing_count = [int]($manifest.missing_count)
        current_dir = [string]$manifest.current_dir
        history_dir = [string]$manifest.history_dir
        missing_files = @($manifest.missing_files)
    }
}

function Get-ExpectedBackupFileNames {
    return @(
        "latest_run.json",
        "latest_run_pretty.json",
        "latest_run_safe_partial.json",
        "latest_run_admin_enriched.json",
        "latest_run_admin_enriched_pretty.json",
        "latest_run_alerted.json",
        "latest_run_alerted_pretty.json",
        "latest_run_intelligence.json",
        "latest_run_intelligence_pretty.json",
        "latest_snapshot.json",
        "snapshot_index.json"
    )
}

# ============================================================
# START
# ============================================================
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Banner "JOM Health Check - $stamp"

# ------------------------------------------------------------
# Check 1: Git state
# ------------------------------------------------------------
try {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $status = git status --porcelain 2>$null
    if ($branch -ne "main") {
        Test-Result 1 "Git state" $false "Not on main branch (on: $branch)" "git checkout main"
    } elseif ($status) {
        Test-Result 1 "Git state" $false "Working tree has uncommitted changes" "git status to inspect"
    } else {
        Test-Result 1 "Git state" $true "Clean, on main"
    }
} catch {
    Test-Result 1 "Git state" $false "Git not responsive" "Confirm git is installed and repo is initialised"
}

# ------------------------------------------------------------
# Check 2: Critical files exist
# ------------------------------------------------------------
$criticalFiles = @(
    "web.py",
    "auth.py",
    "data_collector.py",
    "alert_rules_engine.py",
    "intelligence_rules_engine.py",
    "config\feature_flags.py",
    "scripts\run_operational_snapshot.py",
    "scripts\backup_runtime_chain.py",
    "scripts\restore_runtime_from_backup.ps1"
)
$missing = @()
foreach ($f in $criticalFiles) {
    if (-not (Test-Path $f)) {
        $missing += $f
    }
}
if ($missing.Count -eq 0) {
    Test-Result 2 "Critical files" $true "All $($criticalFiles.Count) expected files present"
} else {
    Test-Result 2 "Critical files" $false "Missing: $($missing -join ', ')" "Confirm files weren't accidentally moved or renamed"
}

# ------------------------------------------------------------
# Check 3: Python imports
# ------------------------------------------------------------
$importTest = @"
import sys
modules = ['auth', 'data_collector', 'alert_rules_engine', 'intelligence_rules_engine', 'web']
failed = []
for m in modules:
    try:
        __import__(m)
    except Exception as e:
        failed.append(f'{m}: {type(e).__name__}')
if failed:
    print('FAIL: ' + '; '.join(failed))
    sys.exit(1)
print('OK')
"@
$importResult = $importTest | python 2>&1
if ($LASTEXITCODE -eq 0 -and $importResult -eq "OK") {
    Test-Result 3 "Python imports" $true "All 5 core modules import OK"
} else {
    Test-Result 3 "Python imports" $false "$importResult" "Check Python path and dependencies"
}

# ------------------------------------------------------------
# Check 4: Phase 2 dormancy
# ------------------------------------------------------------
$dormancyTest = @"
import sys
sys.path.insert(0, '.')
from config.feature_flags import is_enabled
flags = ['multi_user.enabled', 'multi_user.sso_enabled', 'multi_user.allowlist_enforced', 'multi_user.access_audit_enabled']
violations = [f for f in flags if is_enabled(f)]
if violations:
    print('VIOLATIONS: ' + ', '.join(violations))
    sys.exit(1)
print('OK')
"@
$dormancyResult = $dormancyTest | python 2>&1
if ($LASTEXITCODE -eq 0 -and $dormancyResult -eq "OK") {
    Test-Result 4 "Phase 2 dormancy" $true "All 4 multi_user flags FALSE"
} else {
    Test-Result 4 "Phase 2 dormancy" $false "$dormancyResult" "Investigate which flag has been enabled and why"
}

# ------------------------------------------------------------
# Check 5: Feature flag defaults
# ------------------------------------------------------------
$phaseTest = @"
import sys
sys.path.insert(0, '.')
from config.feature_flags import get_phase
print(get_phase())
"@
$phaseResult = $phaseTest | python 2>&1
if ($phaseResult -eq "phase1") {
    Test-Result 5 "Feature flag defaults" $true "phase1 baseline confirmed"
} else {
    Test-Result 5 "Feature flag defaults" $false "Phase reported as: $phaseResult" "Check config/feature_flags.py DEFAULT_FLAGS"
}

# ------------------------------------------------------------
# Check 6: Flask API responding
# ------------------------------------------------------------
try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/source-state" -TimeoutSec 5 -ErrorAction Stop
    if ($response.source_mode -eq "runtime") {
        Test-Result 6 "Flask API" $true "/api/source-state responsive (source_mode=runtime)"
    } else {
        Test-Result 6 "Flask API" $false "Unexpected source_mode: $($response.source_mode)" "Check web.py runtime_source_adapter"
    }
    $script:apiResponse = $response
} catch {
    Test-Result 6 "Flask API" $false "Cannot reach http://127.0.0.1:5000" "Start Flask: python web.py"
    $script:apiResponse = $null
}

# ------------------------------------------------------------
# Check 7: Runtime chain (highest-order file)
# ------------------------------------------------------------
if ($script:apiResponse) {
    $sourceFile = $script:apiResponse.source_file
    if ($sourceFile -like "latest_run_intelligence.json") {
        Test-Result 7 "Runtime chain" $true "$sourceFile is highest-order (best case)"
    } elseif ($sourceFile -like "latest_run_alerted.json") {
        Test-Warning 7 "Runtime chain" "Using $sourceFile (intelligence layer not active)" "Check intelligence_rules_engine.py"
    } else {
        Test-Result 7 "Runtime chain" $false "Source is $sourceFile (low order)" "Investigate why higher-order files arent loading"
    }
} else {
    Test-Result 7 "Runtime chain" $false "Skipped (Flask not responsive)" ""
}

# ------------------------------------------------------------
# Check 8: Scheduled task
# ------------------------------------------------------------
try {
    $task = Get-ScheduledTask -TaskName "JOM_Sync_Runtime" -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskName "JOM_Sync_Runtime"
    if ($task.State -eq "Ready" -and $info.LastTaskResult -eq 0) {
        $nextRun = $info.NextRunTime.ToString("HH:mm")
        Test-Result 8 "Scheduled task" $true "Ready, LastResult=0, next run $nextRun"
    } elseif ($info.LastTaskResult -ne 0) {
        Test-Result 8 "Scheduled task" $false "LastResult=$($info.LastTaskResult)" "Check docs\control\logs\scheduled_sync.log for errors"
    } else {
        Test-Result 8 "Scheduled task" $false "State=$($task.State)" "Check Task Scheduler"
    }
} catch {
    Test-Result 8 "Scheduled task" $false "JOM_Sync_Runtime not registered" "Run scripts\register_scheduled_sync.ps1"
}

# ------------------------------------------------------------
# Check 9: Snapshot retention
# ------------------------------------------------------------
$snapshots = Get-ChildItem snapshots\snapshot_*.json -ErrorAction SilentlyContinue
$regular = $snapshots | Where-Object { $_.Name -notmatch "anchor" }
$anchors = $snapshots | Where-Object { $_.Name -match "anchor" }
$regCount = $regular.Count
$anchCount = $anchors.Count
if ($regCount -le 22 -and $regCount -ge 15) {
    Test-Result 9 "Snapshot retention" $true "$regCount regular + $anchCount anchor (in policy)"
} elseif ($regCount -gt 22) {
    Test-Warning 9 "Snapshot retention" "$regCount regular (over target 20)" "Controller will prune on next run"
} else {
    Test-Result 9 "Snapshot retention" $false "Only $regCount regular snapshots" "Check snapshot_controller.py"
}

# ------------------------------------------------------------
# Check 10: Today's anchor snapshots
# ------------------------------------------------------------
$today = Get-Date -Format "yyyy-MM-dd"
$morningAnchor = Get-ChildItem snapshots\snapshot_${today}*_anchor_morning.json -ErrorAction SilentlyContinue
$eveningAnchor = Get-ChildItem snapshots\snapshot_${today}*_anchor_evening.json -ErrorAction SilentlyContinue
$currentHour = (Get-Date).Hour
if ($morningAnchor -and $eveningAnchor) {
    Test-Result 10 "Anchors today" $true "Morning + evening both present"
} elseif ($morningAnchor -and $currentHour -lt 20) {
    Test-Result 10 "Anchors today" $true "Morning present (evening due 19:55-20:05)"
} elseif (-not $morningAnchor -and $currentHour -lt 8) {
    Test-Result 10 "Anchors today" $true "Pre-morning window (anchors due later)"
} elseif (-not $morningAnchor -and $currentHour -ge 9) {
    Test-Warning 10 "Anchors today" "Morning anchor missing" "Check if scheduler was running 07:55-08:05"
} else {
    Test-Result 10 "Anchors today" $true "In expected state for current time"
}

# ------------------------------------------------------------
# Check 11: Backup manifest freshness
# ------------------------------------------------------------
$backupSummary = Get-BackupManifestSummary -Root $ProjectRoot
$script:backupSummary = $backupSummary
if (-not $backupSummary) {
    Test-Result 11 "Backup manifest" $false "latest_manifest.json not found" "Run python scripts\backup_runtime_chain.py or scripts\run_operational_snapshot.py"
} elseif (-not $backupSummary.parse_ok) {
    Test-Result 11 "Backup manifest" $false "Manifest unreadable: $($backupSummary.error)" "Inspect backups\latest_runtime\latest_manifest.json"
} elseif ($null -eq $backupSummary.age_seconds) {
    Test-Warning 11 "Backup manifest" "Manifest found but backup timestamp could not be parsed" "Inspect created_at_local in latest_manifest.json"
} elseif ($backupSummary.age_seconds -le 1200) {
    Test-Result 11 "Backup manifest" $true "Latest backup age $($backupSummary.age_seconds)s"
} elseif ($backupSummary.age_seconds -le 3600) {
    Test-Warning 11 "Backup manifest" "Latest backup age $($backupSummary.age_seconds)s (stale)" "Confirm scheduled sync is still running"
} else {
    Test-Result 11 "Backup manifest" $false "Latest backup age $($backupSummary.age_seconds)s (too old)" "Run scripts\run_operational_snapshot.py and inspect backup helper"
}

# ------------------------------------------------------------
# Check 12: Backup coverage
# ------------------------------------------------------------
$expectedBackupFiles = Get-ExpectedBackupFileNames
$currentBackupDir = Join-Path $ProjectRoot "backups\latest_runtime\current"
$missingBackupMembers = @()
foreach ($name in $expectedBackupFiles) {
    if (-not (Test-Path (Join-Path $currentBackupDir $name))) {
        $missingBackupMembers += $name
    }
}
if (-not (Test-Path $currentBackupDir)) {
    Test-Result 12 "Backup coverage" $false "Current backup directory missing" "Run python scripts\backup_runtime_chain.py"
} elseif ($missingBackupMembers.Count -eq 0) {
    Test-Result 12 "Backup coverage" $true "All $($expectedBackupFiles.Count) backup members present"
} elseif ($missingBackupMembers.Count -le 2) {
    Test-Warning 12 "Backup coverage" "Partial coverage - missing: $($missingBackupMembers -join ', ')" "Check whether pretty runtime layers are expected in this environment"
} else {
    Test-Result 12 "Backup coverage" $false "Too many backup members missing: $($missingBackupMembers -join ', ')" "Investigate backup_runtime_chain.py outputs"
}

# ------------------------------------------------------------
# Check 13: Secrets protection
# ------------------------------------------------------------
$secrets = @(".env", "tokens.json", ".auth_state.json")
$exposed = @()
foreach ($s in $secrets) {
    if (Test-Path $s) {
        git check-ignore $s 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            $exposed += $s
        }
    }
}
if ($exposed.Count -eq 0) {
    Test-Result 13 "Secrets protection" $true "All $($secrets.Count) secrets gitignored"
} else {
    Test-Result 13 "Secrets protection" $false "Not gitignored: $($exposed -join ', ')" "Add to .gitignore immediately"
}

# ------------------------------------------------------------
# Check 14: Governance pack present
# ------------------------------------------------------------
$governanceFiles = @(
    "docs\governance\JOM_Master_Governance_Delivery_Handover_Pack_v3.docx",
    "docs\governance\JOM_Manager_Stakeholder_Brief_v3.docx",
    "docs\governance\JOM_Phase2_Conversation_Script.docx",
    "docs\security\JOM_Security_Posture_v2.docx",
    "docs\sprints\JOM_Sprint_Deliverables_v2.docx",
    "docs\architecture\MULTI_USER_ARCHITECTURE.md",
    "docs\architecture\SSO_INTEGRATION_PLAN.md",
    "docs\control\mechanics_change_log.md"
)
$missingGov = @()
foreach ($g in $governanceFiles) {
    if (-not (Test-Path $g)) {
        $missingGov += $g
    }
}
if ($missingGov.Count -eq 0) {
    Test-Result 14 "Governance pack" $true "$($governanceFiles.Count) governance files present"
} else {
    Test-Result 14 "Governance pack" $false "Missing: $($missingGov.Count) of $($governanceFiles.Count)" "Check $($missingGov[0])"
}

# ============================================================
# SUMMARY
# ============================================================
Write-Host ""
Write-Host ("=" * 65) -ForegroundColor Cyan
if ($Failed -eq 0) {
    Write-Host "  RESULT: $Passed/$Total PASS - Platform healthy" -ForegroundColor Green
    if ($Warnings -gt 0) {
        Write-Host "  (Includes $Warnings warning(s) - see details above)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  RESULT: $Passed/$Total PASS, $Failed FAILED" -ForegroundColor Red
    Write-Host "  Review failures above and resolve" -ForegroundColor Yellow
}
Write-Host ("=" * 65) -ForegroundColor Cyan
Write-Host ""

if ($Failed -eq 0) {
    exit 0
} else {
    exit 1
}

