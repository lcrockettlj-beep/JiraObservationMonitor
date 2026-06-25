$dataFile = "data/home_summary.json"

if (-not (Test-Path $dataFile)) {
    Write-Host "FAIL: missing home_summary.json"
    return
}

$data = Get-Content $dataFile | ConvertFrom-Json

if ($data.totalUsers -gt 0) {
    Write-Host "OK: users populated"
} else {
    Write-Host "FAIL: users empty"
}

if ($data.lastUpdated) {
    Write-Host "OK: timestamp present"
} else {
    Write-Host "FAIL: missing timestamp"
}
