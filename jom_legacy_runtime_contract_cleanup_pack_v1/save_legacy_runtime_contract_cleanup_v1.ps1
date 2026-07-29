param(
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Location).Path
$PackRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir = Join-Path $RepoRoot "scripts"
$ReportsDir = Join-Path $RepoRoot "reports"

New-Item -ItemType Directory -Force -Path $ScriptsDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null

$Source = Join-Path $PackRoot "scripts\legacy_runtime_contract_cleanup_v1.py"
$Target = Join-Path $ScriptsDir "legacy_runtime_contract_cleanup_v1.py"
Copy-Item -Path $Source -Destination $Target -Force

$ArgsList = @($Target)
if ($SkipSmokeTest) { $ArgsList += "--skip-smoke-test" }

Write-Host "[JOM] Running Legacy Runtime Contract Cleanup v1..." -ForegroundColor Cyan
python @ArgsList

Write-Host ""
Write-Host "[JOM] Report:" -ForegroundColor Green
Write-Host "  reports\legacy_runtime_contract_cleanup_v1.txt"
Write-Host "  reports\legacy_runtime_contract_cleanup_v1.json"
Write-Host ""
Write-Host "[JOM] Review:" -ForegroundColor Cyan
Write-Host "  git diff --stat"
Write-Host "  git status --short"
