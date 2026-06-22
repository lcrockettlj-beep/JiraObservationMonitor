param(
    [string]$Root = ".",
    [string]$OutDir = ".\reports"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Report = Join-Path $OutDir ("sprint10_phase1_audit_" + $Timestamp + ".txt")

$Patterns = @(
    "requests\.",
    "http",
    "atlassian",
    "Authorization",
    "bearer",
    "cloudid",
    "site",
    "sites",
    "403",
    "401",
    "429",
    "500",
    "timeout",
    "exception",
    "latest_run",
    "snapshot",
    "sync_runtime",
    "json.dump"
)

"JOM Sprint 10 Phase 1 Audit" | Set-Content -Path $Report
"Generated: $(Get-Date)" | Add-Content -Path $Report
"" | Add-Content -Path $Report

$Files = Get-ChildItem -Path $Root -Recurse -File -Include *.py,*.ps1,*.js

foreach ($Pattern in $Patterns) {
    "" | Add-Content -Path $Report
    "--- Pattern: $Pattern ---" | Add-Content -Path $Report

    $Hits = $Files | Select-String -Pattern $Pattern -ErrorAction SilentlyContinue

    if ($Hits) {
        foreach ($Hit in $Hits) {
            "$($Hit.Path):$($Hit.LineNumber): $($Hit.Line)" | Add-Content -Path $Report
        }
    } else {
        "(no hits)" | Add-Content -Path $Report
    }
}

Write-Host "Audit complete: $Report"