$folder = "data/sites"

if (-not (Test-Path $folder)) {
    Write-Host "FAIL: missing sites folder"
    return
}

$files = Get-ChildItem $folder -Filter *.json

foreach ($file in $files) {
    $data = Get-Content $file.FullName | ConvertFrom-Json

    if ($data.users -gt 0) {
        Write-Host "OK: $($file.Name)"
    } else {
        Write-Host "FAIL: $($file.Name)"
    }
}
