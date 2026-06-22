
param(
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [string]$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ProjectRoot "reports"
}
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

function Test-Url {
    param(
        [string]$Url,
        [string]$Label
    )
    try {
        $res = Invoke-WebRequest $Url -TimeoutSec 8 -UseBasicParsing
        [PSCustomObject]@{
            label = $Label
            url = $Url
            status = "OK"
            status_code = [int]$res.StatusCode
            content_length = [int]$res.RawContentLength
            message = ""
        }
    }
    catch {
        $statusCode = $null
        try { $statusCode = [int]$_.Exception.Response.StatusCode.value__ } catch {}
        [PSCustomObject]@{
            label = $Label
            url = $Url
            status = "FAILED"
            status_code = $statusCode
            content_length = 0
            message = $_.Exception.Message
        }
    }
}

function Get-HomeSnapshotLine {
    param([string]$Html)
    if ([string]::IsNullOrWhiteSpace($Html)) { return $null }
    $match = [regex]::Match($Html, 'Last verified snapshot:</strong>\s*([^<\r\n]+)')
    if ($match.Success) { return $match.Groups[1].Value.Trim() }
    return $null
}

function Add-RouteIfLiteral {
    param(
        [System.Collections.Generic.HashSet[string]]$Set,
        [string]$Path
    )
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    if ($Path -match '\{\{' -or $Path -match '\{%') { return }
    [void]$Set.Add($Path)
}

Write-Host "`n=== JOM Health Check ===" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Gray
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "Output Dir: $OutputDir" -ForegroundColor Gray

$results = New-Object System.Collections.Generic.List[object]

# Core routes
$coreRoutes = @(
    @{ path = "/"; label = "Home" },
    @{ path = "/estate"; label = "Estate" },
    @{ path = "/reference"; label = "Reference" },
    @{ path = "/detail/change::summary"; label = "Detail change summary" },
    @{ path = "/detail/change::site_attention"; label = "Detail site attention" },
    @{ path = "/detail/project::summary"; label = "Detail project summary" },
    @{ path = "/detail/discovery::summary"; label = "Detail discovery summary" },
    @{ path = "/detail/intelligence::summary"; label = "Detail intelligence summary" },
    @{ path = "/detail/trend::summary"; label = "Detail trend summary" },
    @{ path = "/detail/trend::sites"; label = "Detail trend sites" },
    @{ path = "/api/source-state"; label = "API source state" },
    @{ path = "/api/data"; label = "API data" }
)

Write-Host "`n=== Testing core routes ===" -ForegroundColor Cyan
foreach ($route in $coreRoutes) {
    $fullUrl = "$BaseUrl$($route.path)"
    $r = Test-Url -Url $fullUrl -Label $route.label
    $results.Add($r)
    if ($r.status -eq "OK") {
        Write-Host "$($route.path) OK ($($r.status_code))" -ForegroundColor Green
    } else {
        Write-Host "$($route.path) FAILED ($($r.status_code)) $($r.message)" -ForegroundColor Red
    }
}

# Parse source-state
$sourceState = $null
try {
    $sourceState = Invoke-RestMethod "$BaseUrl/api/source-state" -TimeoutSec 8
} catch {}

# Homepage snapshot text
$homeHtml = $null
$homeSnapshotText = $null
try {
    $homeResponse = Invoke-WebRequest "$BaseUrl/" -TimeoutSec 8 -UseBasicParsing
    $homeHtml = $homeResponse.Content
    $homeSnapshotText = Get-HomeSnapshotLine -Html $homeHtml
} catch {}

# Discover literal href routes from templates
Write-Host "`n=== Discovering literal template routes ===" -ForegroundColor Cyan
$routeSet = New-Object 'System.Collections.Generic.HashSet[string]'
Get-ChildItem (Join-Path $ProjectRoot 'templates') -Filter *.html | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $matches = [regex]::Matches($content, 'href="([^"]+)"')
    foreach ($m in $matches) {
        $href = $m.Groups[1].Value
        if ($href.StartsWith('/detail/') -or $href -eq '/' -or $href -eq '/estate' -or $href -eq '/reference' -or $href -eq '/api/data') {
            Add-RouteIfLiteral -Set $routeSet -Path $href
        }
    }
}

$discovered = $routeSet | Sort-Object
foreach ($path in $discovered) {
    Write-Host $path
}

Write-Host "`n=== Testing discovered literal routes ===" -ForegroundColor Cyan
$discoveredResults = New-Object System.Collections.Generic.List[object]
foreach ($path in $discovered) {
    $label = "Discovered route $path"
    $r = Test-Url -Url "$BaseUrl$path" -Label $label
    $discoveredResults.Add($r)
    $results.Add($r)
    if ($r.status -eq "OK") {
        Write-Host "$path OK ($($r.status_code))" -ForegroundColor Green
    } else {
        Write-Host "$path FAILED ($($r.status_code)) $($r.message)" -ForegroundColor Red
    }
}

# Highlight dynamic trend route explanation
$trendDynamicNote = @"
The route pattern /detail/trend::site:: is not valid by itself.
In templates it is generated as /detail/trend::site::<site_key>, so a real site key must be appended.
"@

# Build summary
$failed = @($results | Where-Object { $_.status -ne 'OK' })
$ok = @($results | Where-Object { $_.status -eq 'OK' })
$summary = [PSCustomObject]@{
    checked_at = (Get-Date).ToString('s')
    base_url = $BaseUrl
    ok_count = $ok.Count
    failed_count = $failed.Count
    source_mode = if ($sourceState) { $sourceState.source_mode } else { $null }
    auto_sync_active = if ($sourceState) { $sourceState.auto_sync_active } else { $null }
    last_sync_time = if ($sourceState) { $sourceState.last_sync_time } else { $null }
    last_sync_age_seconds = if ($sourceState) { $sourceState.last_sync_age_seconds } else { $null }
    anchors_today = if ($sourceState) { $sourceState.anchors_today } else { $null }
    home_last_verified_snapshot_text = $homeSnapshotText
    trend_dynamic_route_note = $trendDynamicNote.Trim()
}

# Save JSON
$jsonPath = Join-Path $OutputDir 'jom_health_check_latest.json'
$payload = [PSCustomObject]@{
    summary = $summary
    results = $results
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -Path $jsonPath -Encoding UTF8

# Save Markdown
$mdPath = Join-Path $OutputDir 'jom_health_check_latest.md'
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# JOM Health Check Report')
$lines.Add('')
$lines.Add("- Checked at: $($summary.checked_at)")
$lines.Add("- Base URL: $($summary.base_url)")
$lines.Add("- OK routes: $($summary.ok_count)")
$lines.Add("- Failed routes: $($summary.failed_count)")
$lines.Add("- Source mode: $($summary.source_mode)")
$lines.Add("- Auto sync active: $($summary.auto_sync_active)")
$lines.Add("- Last sync time: $($summary.last_sync_time)")
$lines.Add("- Last sync age seconds: $($summary.last_sync_age_seconds)")
$lines.Add("- Homepage 'Last verified snapshot' text: $($summary.home_last_verified_snapshot_text)")
$lines.Add('')
$lines.Add('## Dynamic trend route note')
$lines.Add($summary.trend_dynamic_route_note)
$lines.Add('')
$lines.Add('## Route results')
$lines.Add('')
$lines.Add('| Label | URL | Status | Code | Message |')
$lines.Add('|---|---|---:|---:|---|')
foreach ($r in $results) {
    $msg = ($r.message -replace '\|','/' -replace '\r|\n',' ') 
    $lines.Add("| $($r.label) | $($r.url) | $($r.status) | $($r.status_code) | $msg |")
}
Set-Content -Path $mdPath -Value $lines -Encoding UTF8

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "OK: $($summary.ok_count)" -ForegroundColor Green
Write-Host "FAILED: $($summary.failed_count)" -ForegroundColor $(if ($summary.failed_count -gt 0) { 'Red' } else { 'Green' })
Write-Host "Source mode: $($summary.source_mode)"
Write-Host "Auto sync active: $($summary.auto_sync_active)"
Write-Host "Homepage Last verified snapshot text: $($summary.home_last_verified_snapshot_text)"
Write-Host "JSON report: $jsonPath" -ForegroundColor Yellow
Write-Host "Markdown report: $mdPath" -ForegroundColor Yellow
