param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$packRoot   = Join-Path $ProjectRoot "DisabledUsersPack"
$scriptDir  = Join-Path $packRoot "scripts"
$outputDir  = Join-Path $packRoot "output"
$logDir     = Join-Path $packRoot "logs"

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir    | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "disabled_users_$timestamp.log"

Write-Host "=== Disabled Users Pack ===" -ForegroundColor Cyan
"Disabled Users Extraction Log - $timestamp" | Out-File $logFile

function Run-Extract {
    param($Name, $Script)

    Write-Host ">>> $Name" -ForegroundColor Yellow
    "=== $Name ===" | Out-File $logFile -Append

    if (Test-Path $Script) {
        try {
            & $Script -OutputDir $outputDir *>> $logFile
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

Run-Extract "Disabled Users Extraction" (Join-Path $scriptDir "extract_disabled_users.ps1")

Write-Host "`nOutput: $outputDir" -ForegroundColor Green
Write-Host "Log: $logFile" -ForegroundColor Green
