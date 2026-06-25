param([string]$ProjectRoot)

$homeFile    = Join-Path $ProjectRoot "data\home_summary.json"
$estateFile  = Join-Path $ProjectRoot "data\estate_summary.json"

if (-not (Test-Path $homeFile)) {
    Write-Host "FAIL: home_summary.json missing"
    return
}

if (-not (Test-Path $estateFile)) {
    Write-Host "FAIL: estate_summary.json missing"
    return
}

$home   = Get-Content $homeFile | ConvertFrom-Json
$estate = Get-Content $estateFile | ConvertFrom-Json

$home | Add-Member -NotePropertyName "disabled_users_total" -NotePropertyValue $estate.disabled_users_total -Force

$home | ConvertTo-Json -Depth 10 | Set-Content $homeFile

Write-Host "UPDATED: Home disabled total synced"
