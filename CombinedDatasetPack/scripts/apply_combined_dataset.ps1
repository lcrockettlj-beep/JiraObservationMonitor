param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

Write-Host "=== Combined Dataset Pack ===" -ForegroundColor Cyan

$sourceDir = Join-Path $ProjectRoot "DisabledUsersPack\output"
$targetFile = Join-Path $ProjectRoot "data\disabled_users_combined.json"

if (-not (Test-Path $sourceDir)) {
    Write-Host "FAIL: DisabledUsers output not found" -ForegroundColor Red
    exit 1
}

$combined = @()

$files = Get-ChildItem $sourceDir -Filter *.json

foreach ($file in $files) {
    $data = Get-Content $file.FullName | ConvertFrom-Json

    $combined += @{
        site = $data.site
        disabled_count = $data.disabled_count
        disabled_users = $data.disabled_users
    }
}

$combined | ConvertTo-Json -Depth 10 | Set-Content $targetFile

Write-Host "? Combined dataset created:"
Write-Host $targetFile -ForegroundColor Green

