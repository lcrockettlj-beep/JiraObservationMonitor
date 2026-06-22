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

$QuarantineRoot = Join-Path $ProjectRoot ('_cleanup_quarantine\\' + (Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'))
New-Item -ItemType Directory -Path $QuarantineRoot -Force | Out-Null

Write-Host "SAFE CLEANUP APPLY" -ForegroundColor Cyan
Write-Host "Candidates will be MOVED to:" -ForegroundColor Yellow
Write-Host "  $QuarantineRoot" -ForegroundColor Yellow
$confirm = Read-Host "Type MOVE to continue"
if ($confirm -ne 'MOVE') {
  Write-Host "Cleanup cancelled." -ForegroundColor Cyan
  exit 0
}

$found = @()
foreach ($pattern in $Candidates) {
  $items = Get-ChildItem -Path $ProjectRoot -Force -ErrorAction SilentlyContinue -Filter $pattern
  foreach ($item in $items) {
    $found += $item
  }
}
$found = $found | Sort-Object FullName -Unique

foreach ($item in $found) {
  $target = Join-Path $QuarantineRoot $item.Name
  Write-Host "Moving: $($item.FullName)" -ForegroundColor Cyan
  Move-Item -Path $item.FullName -Destination $target -Force
}

Write-Host "Cleanup move complete." -ForegroundColor Green
Write-Host "Review quarantine folder before deleting anything permanently." -ForegroundColor Yellow
