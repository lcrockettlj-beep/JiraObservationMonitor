$dataFile = "data/estate_summary.json"

if (-not (Test-Path $dataFile)) {
    Write-Host "FAIL: missing estate_summary.json"
    return
}

$data = Get-Content $dataFile | ConvertFrom-Json

if ($data.sites.Count -gt 0) {
    Write-Host "OK: sites detected"
} else {
    Write-Host "FAIL: no sites"
}
