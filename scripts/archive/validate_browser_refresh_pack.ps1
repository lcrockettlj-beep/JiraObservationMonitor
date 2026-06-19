$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

$targets = @(
    'static\js\dashboard_refresh.js',
    'templates\home.html',
    'templates\estate.html',
    'templates\reference.html',
    'templates\detail_list.html'
)

foreach ($target in $targets) {
    if (Test-Path $target) {
        Write-Host "FOUND: $target" -ForegroundColor Green
    }
    else {
        Write-Host "MISSING: $target" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Template script-tag check:" -ForegroundColor Cyan
Get-ChildItem .\templates\*.html | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match 'dashboard_refresh\.js') {
        Write-Host "OK: $($_.Name) includes dashboard_refresh.js" -ForegroundColor Green
    }
    else {
        Write-Host "WARN: $($_.Name) does not include dashboard_refresh.js" -ForegroundColor Yellow
    }
}
