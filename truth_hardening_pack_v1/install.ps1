param(
    [string]$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
)

$ErrorActionPreference = "Stop"

Write-Host "=== TRUTH HARDENING PACK v1 INSTALL ===" -ForegroundColor Cyan

Set-Location $ProjectRoot

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups\truth_hardening_v1_$Stamp"

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
New-Item -ItemType Directory -Path ".\static\js" -Force | Out-Null
New-Item -ItemType Directory -Path ".\static\css" -Force | Out-Null

# Install TruthGuard JS
Copy-Item ".\truth_hardening_pack_v1\core_truth_guard.js" ".\static\js\core_truth_guard.js" -Force
Write-Host "Installed static\js\core_truth_guard.js" -ForegroundColor Green

# Create/replace truth.css
@"
.truth-unavailable {
    color: #ff4d4f;
    font-weight: 800;
    text-transform: uppercase;
}

.truth-source {
    display: inline-block;
    margin-top: 6px;
    font-size: 11px;
    opacity: 0.68;
}
"@ | Set-Content ".\static\css\truth.css" -Encoding UTF8

Write-Host "Installed static\css\truth.css" -ForegroundColor Green

# Inject files into templates safely
$Pages = @(
    ".\templates\home.html",
    ".\templates\estate.html",
    ".\templates\reference.html",
    ".\templates\admin.html"
)

foreach ($Page in $Pages) {
    if (-not (Test-Path $Page)) {
        Write-Host "Skipped missing $Page" -ForegroundColor Yellow
        continue
    }

    $BackupPath = Join-Path $BackupRoot $Page
    New-Item -ItemType Directory -Path (Split-Path -Parent $BackupPath) -Force | Out-Null
    Copy-Item $Page $BackupPath -Force

    $Content = Get-Content $Page -Raw

    if ($Content -notmatch "core_truth_guard\.js") {
        $Content = $Content -replace "</head>", "    <script src=`"/static/js/core_truth_guard.js`"></script>`r`n</head>"
        Write-Host "Injected TruthGuard into $Page" -ForegroundColor Green
    }
    else {
        Write-Host "TruthGuard already present in $Page" -ForegroundColor Yellow
    }

    if ($Content -notmatch "truth\.css") {
        $Content = $Content -replace "</head>", "    <link rel=`"stylesheet`" href=`"/static/css/truth.css`">`r`n</head>"
        Write-Host "Injected truth.css into $Page" -ForegroundColor Green
    }
    else {
        Write-Host "truth.css already present in $Page" -ForegroundColor Yellow
    }

    Set-Content $Page $Content -Encoding UTF8
}

Write-Host ""
Write-Host "=== TRUTH HARDENING PACK v1 INSTALL COMPLETE ===" -ForegroundColor Cyan
Write-Host "Backup saved at: $BackupRoot" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next: restart Flask and visually check Home, Estate, Admin." -ForegroundColor White
