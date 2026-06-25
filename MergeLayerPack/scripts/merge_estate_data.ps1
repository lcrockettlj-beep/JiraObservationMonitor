param([string]$ProjectRoot)

$estateFile  = Join-Path $ProjectRoot "data\estate_summary.json"
$disabledDir = Join-Path $ProjectRoot "DisabledUsersPack\output"

if (-not (Test-Path $estateFile)) {
    Write-Host "FAIL: estate_summary.json missing"
    return
}

$total = 0

$files = Get-ChildItem $disabledDir -Filter *.json
foreach ($file in $files) {
    $data = Get-Content $file.FullName | ConvertFrom-Json
    $total += $data.disabled_count
}

$estate = Get-Content $estateFile | ConvertFrom-Json

$estate | Add-Member -NotePropertyName "disabled_users_total" -NotePropertyValue $total -Force

$estate | ConvertTo-Json -Depth 10 | Set-Content $estateFile

Write-Host "UPDATED: Estate total disabled = $total"
