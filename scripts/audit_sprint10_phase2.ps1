param(
    [string]$Root = ".",
    [string]$OutDir = ".\reports"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$Timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Report = Join-Path $OutDir ("sprint10_phase2_audit_" + $Timestamp + ".txt")

$Patterns = @(
    "latest_run",
    "latest_run_pretty",
    "latest_run_admin_enriched",
    "latest_run_alerted",
    "latest_run_intelligence",
    "latest_snapshot",
    "snapshot_index",
    "snapshot_",
    "snapshots",
    "backup",
    "restore",
    "rollback",
    "copy",
    "Copy-Item",
    "shutil",
    "write_text",
    "json.dump",
    "json.dumps",
    "safe_json_write",
    "snapshot_controller",
    "sync_runtime",
    "validate_contract",
    "change_tracker",
    "source-state",
    "source_state"
)

"JOM Sprint 10 Phase 2 Audit" | Set-Content -Path $Report -Encoding UTF8
"Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content -Path $Report -Encoding UTF8
"Root: $(Resolve-Path $Root)" | Add-Content -Path $Report -Encoding UTF8
"" | Add-Content -Path $Report -Encoding UTF8
"=== PRIORITY FILES ===" | Add-Content -Path $Report -Encoding UTF8
@(
    ".\\snapshots.py",
    ".\\scripts\\snapshot_controller.py",
    ".\\scripts\\sync_runtime.py",
    ".\\web.py",
    ".\\data_collector.py",
    ".\\admin_api_enrichment.py",
    ".\\scripts\\health_check.ps1",
    ".\\scripts\\jom_health_check.ps1"
) | ForEach-Object {
    if (Test-Path $_) { $_ | Add-Content -Path $Report -Encoding UTF8 }
}

"" | Add-Content -Path $Report -Encoding UTF8
"=== PATTERN HITS ===" | Add-Content -Path $Report -Encoding UTF8

$Files = Get-ChildItem -Path $Root -Recurse -File -Include *.py,*.ps1,*.cmd,*.js,*.html,*.jinja

foreach ($Pattern in $Patterns) {
    "" | Add-Content -Path $Report -Encoding UTF8
    "--- Pattern: $Pattern ---" | Add-Content -Path $Report -Encoding UTF8
    $Hits = $Files | Select-String -Pattern $Pattern -CaseSensitive:$false
    if ($Hits) {
        foreach ($Hit in $Hits) {
            $Line = $Hit.Line.Trim()
            "{0}:{1}: {2}" -f $Hit.Path, $Hit.LineNumber, $Line | Add-Content -Path $Report -Encoding UTF8
        }
    }
    else {
        "(no hits)" | Add-Content -Path $Report -Encoding UTF8
    }
}

"" | Add-Content -Path $Report -Encoding UTF8
"=== PHASE 2 REVIEW QUESTIONS ===" | Add-Content -Path $Report -Encoding UTF8
"1. Where is the definitive latest runtime written, and in what order across collection -> enrichment -> alerting -> intelligence?" | Add-Content -Path $Report -Encoding UTF8
"2. What current rollback material already exists (snapshots, latest_snapshot.json, latest_run_safe_partial.json)?" | Add-Content -Path $Report -Encoding UTF8
"3. Where should a secondary backup copy be written so a bad fresh write cannot strand the monitor?" | Add-Content -Path $Report -Encoding UTF8
"4. Which script should own restore operations: snapshots.py, snapshot_controller.py, or a new restore_runtime.ps1?" | Add-Content -Path $Report -Encoding UTF8

Write-Host "Audit complete: $Report"
