param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

$scriptDir = Join-Path $ProjectRoot "LicenseMergeUIPack\scripts"

function Run-Step {
    param($Name, $Script)

    Write-Host ">>> $Name" -ForegroundColor Yellow

    if (Test-Path $Script) {
        try {
            & $Script -ProjectRoot $ProjectRoot
            Write-Host "PASS" -ForegroundColor Green
        } catch {
            Write-Host "FAIL" -ForegroundColor Red
        }
    } else {
        Write-Host "MISSING SCRIPT" -ForegroundColor Red
    }
}

Run-Step "Merge Site License"  (Join-Path $scriptDir "merge_license_sites.ps1")
Run-Step "Merge Estate"        (Join-Path $scriptDir "merge_license_estate.ps1")
Run-Step "Merge Home"          (Join-Path $scriptDir "merge_license_home.ps1")
Run-Step "Apply UI"            (Join-Path $scriptDir "apply_license_ui.ps1")

Write-Host "`n? License Merge + UI Complete" -ForegroundColor Green
