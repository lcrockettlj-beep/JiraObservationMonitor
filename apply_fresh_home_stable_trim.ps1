param(
    [string]$ProjectRoot = "$env:USERPROFILE\Desktop\JiraObservationMonitor",
    [string]$ZipName = "fresh_home_stable_trim_pack.zip"
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) {
    Write-Host "[INFO] $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "[OK]   $msg" -ForegroundColor Green
}

function Write-WarnMsg($msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Fail($msg) {
    Write-Host "[FAIL] $msg" -ForegroundColor Red
    exit 1
}

Write-Info "Starting Home Stable Trim pack apply script"
Write-Info "ProjectRoot = $ProjectRoot"
Write-Info "ZipName     = $ZipName"

if (-not (Test-Path $ProjectRoot)) {
    Fail "Project root does not exist: $ProjectRoot"
}

$expectedDirs = @(
    (Join-Path $ProjectRoot 'static\css'),
    (Join-Path $ProjectRoot 'static\js'),
    (Join-Path $ProjectRoot 'templates')
)

foreach ($dir in $expectedDirs) {
    if (-not (Test-Path $dir)) {
        Fail "Expected project folder missing: $dir"
    }
}

$downloadZip = Join-Path $env:USERPROFILE ("Downloads\" + $ZipName)
$localZip    = Join-Path $ProjectRoot $ZipName

if (Test-Path $downloadZip) {
    Write-Info "Found zip in Downloads: $downloadZip"
    Copy-Item $downloadZip $localZip -Force
    Write-Ok "Copied zip into project root"
}
elseif (Test-Path $localZip) {
    Write-WarnMsg "Zip already exists in project root: $localZip"
}
else {
    Fail "Could not find $ZipName in Downloads or project root. Download the zip from chat first."
}

$backupStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupRoot  = Join-Path $ProjectRoot ("backup_home_stable_trim_" + $backupStamp)
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $backupRoot 'static\css') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $backupRoot 'static\js') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $backupRoot 'templates') -Force | Out-Null

$filesToBackup = @(
    @{src = Join-Path $ProjectRoot 'static\css\app.css'; dst = Join-Path $backupRoot 'static\css\app.css'},
    @{src = Join-Path $ProjectRoot 'static\css\home.css'; dst = Join-Path $backupRoot 'static\css\home.css'},
    @{src = Join-Path $ProjectRoot 'static\js\dashboard_refresh.js'; dst = Join-Path $backupRoot 'static\js\dashboard_refresh.js'},
    @{src = Join-Path $ProjectRoot 'templates\home.html'; dst = Join-Path $backupRoot 'templates\home.html'},
    @{src = Join-Path $ProjectRoot 'templates\_nav.html'; dst = Join-Path $backupRoot 'templates\_nav.html'}
)

foreach ($item in $filesToBackup) {
    if (Test-Path $item.src) {
        Copy-Item $item.src $item.dst -Force
    }
}
Write-Ok "Backed up current Home files to: $backupRoot"

$tempExtract = Join-Path $env:TEMP ("fresh_home_stable_trim_" + $backupStamp)
if (Test-Path $tempExtract) {
    Remove-Item $tempExtract -Recurse -Force
}
New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null

Expand-Archive -Path $localZip -DestinationPath $tempExtract -Force
Write-Ok "Expanded zip to temporary folder"

$expectedFiles = @(
    'static\css\app.css',
    'static\css\home.css',
    'static\js\dashboard_refresh.js',
    'templates\home.html',
    'templates\_nav.html'
)

foreach ($rel in $expectedFiles) {
    $full = Join-Path $tempExtract $rel
    if (-not (Test-Path $full)) {
        Fail "Zip validation failed. Missing file inside zip: $rel"
    }
}
Write-Ok "Zip validation passed"

Copy-Item (Join-Path $tempExtract 'static\css\app.css') (Join-Path $ProjectRoot 'static\css\app.css') -Force
Copy-Item (Join-Path $tempExtract 'static\css\home.css') (Join-Path $ProjectRoot 'static\css\home.css') -Force
Copy-Item (Join-Path $tempExtract 'static\js\dashboard_refresh.js') (Join-Path $ProjectRoot 'static\js\dashboard_refresh.js') -Force
Copy-Item (Join-Path $tempExtract 'templates\home.html') (Join-Path $ProjectRoot 'templates\home.html') -Force
Copy-Item (Join-Path $tempExtract 'templates\_nav.html') (Join-Path $ProjectRoot 'templates\_nav.html') -Force
Write-Ok "Applied fresh stable trim files into project"

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Refresh the app in browser with Ctrl + F5" -ForegroundColor White
Write-Host "  2. Verify Stable Sites cards are compact" -ForegroundColor White
Write-Host "  3. If happy, commit with:" -ForegroundColor White
Write-Host "     git add .\static\css\app.css .\static\css\home.css .\static\js\dashboard_refresh.js .\templates\home.html .\templates\_nav.html" -ForegroundColor Gray
Write-Host "     git commit -m \"UI Home: trim stable site cards and keep deep metrics for site pages\"" -ForegroundColor Gray
Write-Host "     git push" -ForegroundColor Gray
Write-Host ""
Write-Ok "Done"
