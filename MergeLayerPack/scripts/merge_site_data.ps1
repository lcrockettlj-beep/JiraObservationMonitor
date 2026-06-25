param([string]$ProjectRoot)

$dataDir     = Join-Path $ProjectRoot "data\sites"
$disabledDir = Join-Path $ProjectRoot "DisabledUsersPack\output"

$files = Get-ChildItem $dataDir -Filter *.json

foreach ($file in $files) {
    $siteName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $disabledFile = Join-Path $disabledDir "$siteName-disabled.json"

    if (-not (Test-Path $disabledFile)) {
        Write-Host "SKIP: $siteName (no disabled data)"
        continue
    }

    $siteData     = Get-Content $file.FullName | ConvertFrom-Json
    $disabledData = Get-Content $disabledFile | ConvertFrom-Json

    $siteData | Add-Member -NotePropertyName "disabled_count" -NotePropertyValue $disabledData.disabled_count -Force

    $siteData | ConvertTo-Json -Depth 10 | Set-Content $file.FullName

    Write-Host "UPDATED: $siteName ($($disabledData.disabled_count) disabled)"
}
