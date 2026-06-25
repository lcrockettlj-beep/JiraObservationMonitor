param([string]$ProjectRoot)

Write-Host "=== Aligned Merge Pack ===" -ForegroundColor Cyan

$runtimeFile = Join-Path $ProjectRoot "latest_run_pretty.json"
$disabledDir = Join-Path $ProjectRoot "DisabledUsersPack\output"
$licenseDir  = Join-Path $ProjectRoot "LicenseUsagePack\output"

if (-not (Test-Path $runtimeFile)) {
    Write-Host "FAIL: runtime file missing" -ForegroundColor Red
    exit 1
}

$runtime = Get-Content $runtimeFile | ConvertFrom-Json

# ==========================
# DISABLED USERS
# ==========================
$disabledTotal = 0

Get-ChildItem $disabledDir -Filter *.json | ForEach-Object {
    $d = Get-Content $_.FullName | ConvertFrom-Json
    $disabledTotal += $d.disabled_count
}

$runtime | Add-Member disabled_users_total $disabledTotal -Force

# ==========================
# LICENSE COUNTS
# ==========================
$jiraTotal = 0
$confTotal = 0

Get-ChildItem $licenseDir -Filter *.json | ForEach-Object {
    $l = Get-Content $_.FullName | ConvertFrom-Json
    $jiraTotal += $l.jira_users
    $confTotal += $l.confluence_users
}

$runtime | Add-Member jira_users_total $jiraTotal -Force
$runtime | Add-Member confluence_users_total $confTotal -Force

# ==========================
# SAVE BACK
# ==========================
$runtime | ConvertTo-Json -Depth 20 | Set-Content $runtimeFile

Write-Host "? Runtime enriched (disabled + license)" -ForegroundColor Green

