param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$packRoot   = Join-Path $ProjectRoot "MergeLayerPack"
$scriptDir  = Join-Path $packRoot "scripts"
$logDir     = Join-Path $packRoot "logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "merge_layer_$timestamp.log"

Write-Host "=== Merge Layer Pack ===" -ForegroundColor Cyan
"Merge Layer Log - $timestamp" | Out-File $logFile

function Run-Step {
    param($Name, $Script)

    Write-Host ">>> $Name" -ForegroundColor Yellow
    "=== $Name ===" | Out-File $logFile -Append

    if (Test-Path $Script) {
        try {
            & $Script -ProjectRoot $ProjectRoot *>> $logFile
            Write-Host "PASS" -ForegroundColor Green
        } catch {
            Write-Host "FAIL" -ForegroundColor Red
            $_ | Out-File $logFile -Append
        }
    } else {
        Write-Host "MISSING SCRIPT" -ForegroundColor Red
    }

    "" | Out-File $logFile -Append
}

Run-Step "Merge Site Data"    (Join-Path $scriptDir "merge_site_data.ps1")
Run-Step "Merge Estate Data"  (Join-Path $scriptDir "merge_estate_data.ps1")
Run-Step "Merge Home Data"    (Join-Path $scriptDir "merge_home_data.ps1")

Write-Host "`nLog: $logFile" -ForegroundColor Green
