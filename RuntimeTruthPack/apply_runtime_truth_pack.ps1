param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$packRoot  = Join-Path $ProjectRoot "RuntimeTruthPack"
$scriptDir = Join-Path $packRoot "scripts"
$logDir    = Join-Path $packRoot "logs"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "runtime_truth_$timestamp.log"

function Run-Test {
    param($Name, $Path)

    Write-Host ">>> $Name" -ForegroundColor Cyan
    "=== $Name ===" | Out-File $logFile -Append

    if (Test-Path $Path) {
        try {
            & $Path *>> $logFile
            Write-Host "PASS" -ForegroundColor Green
            "STATUS: PASS" | Out-File $logFile -Append
        }
        catch {
            Write-Host "FAIL (exec error)" -ForegroundColor Red
            $_ | Out-File $logFile -Append
            "STATUS: FAIL" | Out-File $logFile -Append
        }
    }
    else {
        Write-Host "FAIL (missing script)" -ForegroundColor Red
        "STATUS: FAIL (missing)" | Out-File $logFile -Append
    }

    "" | Out-File $logFile -Append
}

Run-Test "API Connectivity" (Join-Path $scriptDir "test_api_connectivity.ps1")
Run-Test "Home Data"        (Join-Path $scriptDir "test_home_data.ps1")
Run-Test "Estate Data"      (Join-Path $scriptDir "test_estate_data.ps1")
Run-Test "Site Data"        (Join-Path $scriptDir "test_site_data.ps1")

Write-Host "`nLog: $logFile" -ForegroundColor Green
