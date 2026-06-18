$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

$templates = @(
    'templates\home.html',
    'templates\estate.html',
    'templates\reference.html',
    'templates\detail_list.html'
)

$scriptTag = '  <script src="{{ url_for(''static'', filename=''js/dashboard_refresh.js'') }}"></script>'
$backupDir = Join-Path $ProjectRoot ("browser_refresh_backups\" + (Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'))
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

foreach ($template in $templates) {
    if (-not (Test-Path $template)) {
        Write-Host "Skipping missing template: $template" -ForegroundColor Yellow
        continue
    }

    $content = Get-Content $template -Raw
    if ($content -match 'dashboard_refresh\.js') {
        Write-Host "Already patched: $template" -ForegroundColor Green
        continue
    }

    $targetBackup = Join-Path $backupDir ([IO.Path]::GetFileName($template))
    Copy-Item $template $targetBackup -Force

    if ($content -match '</body>') {
        $updated = $content -replace '</body>', ($scriptTag + "`r`n</body>")
    }
    else {
        $updated = $content.TrimEnd() + "`r`n" + $scriptTag + "`r`n"
    }

    Set-Content -Path $template -Value $updated -Encoding UTF8
    Write-Host "Patched: $template" -ForegroundColor Cyan
}

Write-Host "Backups saved to: $backupDir" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Make sure static\js\dashboard_refresh.js exists"
Write-Host "  2. Run python web.py"
Write-Host "  3. Open / and confirm the Live Runtime badge appears"
