param([string]$ProjectRoot)

$dataDir    = Join-Path $ProjectRoot "data\sites"
$licenseDir = Join-Path $ProjectRoot "LicenseUsagePack\output"

$files = Get-ChildItem $dataDir -Filter *.json

foreach ($file in $files) {
    $siteName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $licenseFile = Join-Path $licenseDir "$siteName-license.json"

    if (-not (Test-Path $licenseFile)) {
        Write-Host "SKIP: $siteName"
        continue
    }

    $site = Get-Content $file.FullName | ConvertFrom-Json
    $license = Get-Content $licenseFile | ConvertFrom-Json

    $site | Add-Member jira_users $license.jira_users -Force
    $site | Add-Member confluence_users $license.confluence_users -Force

    $site | ConvertTo-Json -Depth 10 | Set-Content $file.FullName

    Write-Host "UPDATED: $siteName"
}
