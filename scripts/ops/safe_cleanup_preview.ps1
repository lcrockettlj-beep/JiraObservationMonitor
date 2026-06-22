$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

$Candidates = @(
  'UI_LAYER_*',
  'backup_ui_layer*',
  'archive_full_dump',
  'recovery',
  '*.zip',
  '*.csv',
  'auth_from_rescue.py',
  'auth_verification_report.json',
  'auth_verification_report.txt',
  'browser_refresh_backups'
)

Write-Host "Safe cleanup preview only. Nothing will be moved or deleted." -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor Yellow
Write-Host "" 

$found = @()
foreach ($pattern in $Candidates) {
  $items = Get-ChildItem -Path $ProjectRoot -Force -ErrorAction SilentlyContinue -Filter $pattern
  foreach ($item in $items) {
    $found += $item
  }
}

$found = $found | Sort-Object FullName -Unique
if (-not $found) {
  Write-Host "No cleanup candidates found from the default patterns." -ForegroundColor Green
  exit 0
}

$found | Select-Object FullName, PSIsContainer, Length, LastWriteTime | Format-Table -AutoSize

Write-Host "" 
Write-Host "Recommended exclusions (do NOT clean):" -ForegroundColor Yellow
Write-Host "- .env"
Write-Host "- tokens.json"
Write-Host "- .auth_state.json"
Write-Host "- latest_run*.json"
Write-Host "- snapshots\"
Write-Host "- backend\"
Write-Host "- static\"
Write-Host "- templates\"
Write-Host "- web.py / auth.py / data_collector.py / admin_api_*.py / alert_rules_engine.py / intelligence_rules_engine.py"
