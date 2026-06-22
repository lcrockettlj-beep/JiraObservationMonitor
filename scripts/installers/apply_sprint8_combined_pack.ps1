param(
    [string]$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Backup-File {
    param([string]$Path)
    if (Test-Path $Path) {
        Copy-Item $Path "$Path.bak" -Force
        Write-Host "Backed up: $Path -> $Path.bak" -ForegroundColor Yellow
    }
}

function Write-Utf8NoBom {
    param([string]$Path,[string]$Content)
    $dir = Split-Path $Path -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Wrote: $Path" -ForegroundColor Green
}

Set-Location $ProjectRoot
Write-Step "Applying Sprint 8 combined pack"
Write-Host "Project root: $(Get-Location)" -ForegroundColor Gray

Write-Step "Backing up current templates"
Backup-File "templates\estate.html"
Backup-File "templates\reference.html"
Backup-File "templates\detail_list.html"

$estateHtml = @'
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Estate Page - Jira Observation Monitor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="{{ url_for('static', filename='js/theme.js') }}"></script>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/home.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/estate.css') }}">
</head>
<body>
<div class="page">
    {% include "_nav.html" %}
    <section class="hero">
        <div class="hero__top">
            <div>
                <div class="hero__back"><a href="/" class="text-link">&larr; Back to operational overview</a></div>
                <h1>Estate Overview</h1>
                <p>Live view of the monitored Jira estate, including sites in scope, excluded sites, and discovery candidates that may need review.</p>
            </div>
            <div class="hero__meta">
                <div class="pill"><a href="/reference">Reference area</a></div>
                <div class="pill"><a href="/detail/discovery::summary">View discovery summary</a></div>
            </div>
        </div>
    </section>
    {% set discovery_summary = site_discovery.get("summary", {}) if site_discovery else {} %}
    <section class="section">
        <div class="section__header">
            <h2>Estate Registry</h2>
            <div class="count"><a href="/detail/discovery::summary">Open full discovery summary</a></div>
        </div>
        <div class="estate-grid">
            <a href="/detail/discovery::tracked_sites" class="estate-card"><div class="estate-title">Sites monitored</div><div class="estate-value">{{ discovery_summary.tracked_site_count if discovery_summary else 0 }}</div><div class="estate-sub">Operational Jira sites currently in scope.</div></a>
            <a href="/detail/discovery::excluded_sites" class="estate-card"><div class="estate-title">Sites excluded</div><div class="estate-value">{{ discovery_summary.excluded_site_count if discovery_summary else 0 }}</div><div class="estate-sub">Sites identified but currently outside monitoring scope.</div></a>
            <a href="/detail/discovery::all_sites" class="estate-card"><div class="estate-title">Sites discovered</div><div class="estate-value">{{ discovery_summary.discovered_site_count if discovery_summary else 0 }}</div><div class="estate-sub">Combined view of all tracked and excluded sites.</div></a>
            <a href="/detail/discovery::new_site_candidates" class="estate-card"><div class="estate-title">Sites to review</div><div class="estate-value">{{ discovery_summary.new_site_candidate_count if discovery_summary else 0 }}</div><div class="estate-sub">Potential new sites that may need classification.</div></a>
        </div>
    </section>
    <section class="estate-split">
        <div class="panel estate-panel">
            <div class="section__header"><h2>Discovery actions</h2><div class="count">Registry drilldowns</div></div>
            <div class="breakdown-list">
                <a href="/detail/discovery::tracked_sites" class="breakdown-row clickable"><div class="breakdown-row__label">View monitored sites</div><div class="breakdown-row__value">{{ discovery_summary.tracked_site_count if discovery_summary else 0 }}</div></a>
                <a href="/detail/discovery::excluded_sites" class="breakdown-row clickable"><div class="breakdown-row__label">View excluded sites</div><div class="breakdown-row__value">{{ discovery_summary.excluded_site_count if discovery_summary else 0 }}</div></a>
                <a href="/detail/discovery::all_sites" class="breakdown-row clickable"><div class="breakdown-row__label">View all discovered sites</div><div class="breakdown-row__value">{{ discovery_summary.discovered_site_count if discovery_summary else 0 }}</div></a>
                <a href="/detail/discovery::new_site_candidates" class="breakdown-row clickable"><div class="breakdown-row__label">View sites to review</div><div class="breakdown-row__value">{{ discovery_summary.new_site_candidate_count if discovery_summary else 0 }}</div></a>
            </div>
        </div>
        <div class="panel estate-panel">
            <div class="section__header"><h2>Operational actions</h2><div class="count">Drilldowns and summaries</div></div>
            <div class="breakdown-list">
                <a href="/detail/change::summary" class="breakdown-row clickable"><div class="breakdown-row__label">Change summary</div><div class="breakdown-row__value">Open</div></a>
                <a href="/detail/change::site_attention" class="breakdown-row clickable"><div class="breakdown-row__label">Sites needing attention</div><div class="breakdown-row__value">Open</div></a>
                <a href="/detail/project::summary" class="breakdown-row clickable"><div class="breakdown-row__label">Project summary</div><div class="breakdown-row__value">Open</div></a>
                <a href="/api/data" class="breakdown-row clickable"><div class="breakdown-row__label">Raw platform data</div><div class="breakdown-row__value">JSON</div></a>
            </div>
        </div>
    </section>
    <section class="section"><div class="section__header"><h2>Operational site health</h2><div class="count">Estate-wide site review</div></div></section>
    {{ site_section('Critical sites', critical_sites|length, critical_sites, 'critical') }}
    {{ site_section('Warning sites', warning_sites|length, warning_sites, 'warning') }}
    {{ site_section('Stable sites', stable_sites|length, stable_sites, 'stable') }}
</div>
<script>window.JOMTheme.initToggle("theme-toggle");</script>
<script src="{{ url_for('static', filename='js/dashboard_refresh.js') }}"></script>
</body>
</html>
'@

$referenceHtml = @'
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Reference Page - Jira Observation Monitor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="{{ url_for('static', filename='js/theme.js') }}"></script>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/home.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/reference.css') }}">
</head>
<body>
<div class="page">
    {% include "_nav.html" %}
    <section class="hero">
        <div class="hero__top">
            <div>
                <div class="hero__back"><a href="/" class="text-link">&larr; Back to operational overview</a></div>
                <h1>Reference Area</h1>
                <p>Supporting reference views for products, billing coverage, and user access breakdowns.</p>
            </div>
            <div class="hero__meta">
                <div class="pill"><a href="/estate">Open estate page</a></div>
                <div class="pill"><a href="/detail/project::summary">Project summary</a></div>
            </div>
        </div>
    </section>
    <div class="reference-grid">
        <div class="reference-panel">
            <div class="section__header"><h2>Products in use</h2><div class="count">Select a product to inspect users</div></div>
            {% if org_product_breakdown %}
            <div class="reference-list">{% for item in org_product_breakdown %}<a href="/detail/product::{{ item.key }}" class="reference-row"><div class="reference-label">{{ item.label }}</div><div class="reference-value">{{ item.count }}</div></a>{% endfor %}</div>
            {% else %}
            <div class="empty">No product breakdown is currently available.</div>
            {% endif %}
        </div>
        <div class="reference-panel">
            <div class="section__header"><h2>Billing & marketplace coverage</h2><div class="count">Select an area to inspect app entries</div></div>
            <div class="reference-list">
                <a href="/detail/billing::atlassian_apps" class="reference-row"><div class="reference-label">Atlassian app entries</div><div class="reference-value">{{ billing_summary.atlassian_app_entry_count or 0 }}</div></a>
                <a href="/detail/billing::marketplace_apps" class="reference-row"><div class="reference-label">Marketplace app entries</div><div class="reference-value">{{ billing_summary.marketplace_app_entry_count or 0 }}</div></a>
                <a href="/detail/billing::jira_entries" class="reference-row"><div class="reference-label">Jira billing entries</div><div class="reference-value">{{ billing_summary.unique_jira_entries or 0 }}</div></a>
                <a href="/detail/billing::bitbucket_entries" class="reference-row"><div class="reference-label">Bitbucket billing entries</div><div class="reference-value">{{ billing_summary.unique_bitbucket_entries or 0 }}</div></a>
                <a href="/detail/billing::confluence_entries" class="reference-row"><div class="reference-label">Confluence billing entries</div><div class="reference-value">{{ billing_summary.unique_confluence_entries or 0 }}</div></a>
                <a href="/detail/billing::rovo_entries" class="reference-row"><div class="reference-label">Rovo billing entries</div><div class="reference-value">{{ billing_summary.unique_rovo_entries or 0 }}</div></a>
            </div>
        </div>
    </div>
    <section class="section">
        <div class="section__header"><h2>User access breakdown</h2><div class="count">Select an access area to inspect users</div></div>
        {% if users_export_breakdown %}
        <div class="panel reference-panel-inline"><div class="breakdown-list">{% for item in users_export_breakdown %}<a href="/detail/access::{{ item.key }}" class="breakdown-row clickable"><div class="breakdown-row__label">{{ item.label }}</div><div class="breakdown-row__value">{{ item.count }}</div></a>{% endfor %}</div></div>
        {% else %}
        <div class="empty">No user access breakdown is currently available.</div>
        {% endif %}
    </section>
</div>
<script>window.JOMTheme.initToggle("theme-toggle");</script>
<script src="{{ url_for('static', filename='js/dashboard_refresh.js') }}"></script>
</body>
</html>
'@

$detailHtml = @'
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{{ title or "Detail" }} - Jira Observation Monitor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="{{ url_for('static', filename='js/theme.js') }}"></script>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/detail.css') }}">
</head>
<body>
<div class="page">
    {% include "_nav.html" %}
    <section class="hero">
        <div class="hero__top">
            <div>
                <div class="hero__back"><a href="/" class="text-link">&larr; Back to operational overview</a></div>
                <h1>{{ title }}</h1>
                <p>Reason for this view: {{ reason }}</p>
                <p class="detail-context">Where to look in Atlassian: {{ atlassian_area }}</p>
            </div>
            <div class="hero__meta">
                <div class="pill">{{ rows|length }} record(s)</div>
                <div class="pill">Click a column heading to sort</div>
            </div>
        </div>
    </section>
    <section class="panel">
        <div class="section__header"><h2>{{ title }}</h2><div class="count">{{ detail_key }}</div></div>
        {% if rows %}
        <div class="table-wrap"><table><thead><tr>{% for col in columns %}{% set is_current = (sort_key == col) %}{% set next_order = 'desc' if (is_current and sort_order != 'desc') else 'asc' %}<th><a href="?sort={{ col|urlencode }}&order={{ next_order }}">{{ col.replace('_', ' ') }}{% if is_current %}<span>{{ '&darr;' if sort_order == 'desc' else '&uarr;' }}</span>{% endif %}</a></th>{% endfor %}</tr></thead><tbody>{% for row in rows %}<tr>{% for col in columns %}{% set value = row.get(col, '') %}<td class="{{ 'wrap' if (value|string)|length > 60 else '' }}">{{ value }}</td>{% endfor %}</tr>{% endfor %}</tbody></table></div>
        {% else %}
        <div class="empty">No records are currently available for this view.</div>
        {% endif %}
    </section>
</div>
<script>window.JOMTheme.initToggle("theme-toggle");</script>
<script src="{{ url_for('static', filename='js/dashboard_refresh.js') }}"></script>
</body>
</html>
'@

$estateCss = @'
.estate-grid { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin-bottom:20px; }
.estate-card { background:var(--panel); border:1px solid var(--border); border-radius:18px; padding:18px; display:block; }
.estate-card:hover { border-color:rgba(69,155,227,0.45); background:rgba(255,255,255,0.06); }
.estate-title { font-size:14px; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:10px; }
.estate-value { font-size:32px; font-weight:700; line-height:1; margin-bottom:8px; }
.estate-sub { font-size:13px; color:var(--muted); line-height:1.5; }
.estate-split { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:22px; }
.estate-panel { padding:18px; }
.hero__back { margin-bottom:10px; }
.metric-inline-note { margin-top:6px; font-size:12px; color:var(--muted); }
.site-flags { margin-bottom:10px; display:flex; gap:6px; flex-wrap:wrap; font-size:11px; }
.status-pill { padding:4px 8px; border-radius:999px; }
.status-pill--good { background:rgba(45,190,127,0.15); border:1px solid rgba(45,190,127,0.4); }
.status-pill--warning { background:rgba(240,178,74,0.15); border:1px solid rgba(240,178,74,0.4); }
.status-pill--critical { background:rgba(225,75,90,0.15); border:1px solid rgba(225,75,90,0.4); }
.usage-row--spaced { margin-top:8px; }
@media (max-width: 1160px) { .estate-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); } .estate-split { grid-template-columns:1fr; } }
@media (max-width: 760px) { .estate-grid { grid-template-columns:1fr; } }
'@

$referenceCss = @'
.reference-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }
.reference-panel { background:var(--panel); border:1px solid var(--border); border-radius:20px; padding:18px; }
.reference-panel-inline { padding:18px; }
.reference-list { display:grid; gap:10px; }
.reference-row { display:flex; justify-content:space-between; gap:12px; align-items:center; padding:12px 14px; border-radius:14px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); }
.reference-row:hover { border-color:rgba(69, 155, 227, 0.45); background:rgba(255,255,255,0.06); }
.reference-label { color:var(--text); }
.reference-value { color:var(--text); font-weight:700; }
.hero__back { margin-bottom:10px; }
@media (max-width: 980px) { .reference-grid { grid-template-columns:1fr; } }
'@

$progressArchive = @'
# Sprint 8 Progress Archive

**Checkpoint date:** 22 June 2026  
**Phase:** Sprint 8 — Frontend Alignment & Refresh  
**Status:** In progress

## What has been completed
### Pillar 1 — Foundation
- Shared navigation extracted into `templates/_nav.html`
- GLI logo integrated into shared nav
- Light/dark mode logo contrast issue corrected
- Shared nav applied across all main pages

### Pillar 2 — Homepage UX alignment
- Homepage source-strip changed from internal file references to operator-facing status indicators
- Engineer-oriented labels replaced with operator-friendly language on homepage
- Hero text and section descriptions rewritten for non-technical readability
- Homepage cards reduced in noise and signal hierarchy improved

### Pillar 3 — Visual branding and readability
- GLI font integrated
- Dark mode readability corrected
- Intelligence cards given glow hierarchy
- Site cards improved with warning/critical signal styling
- Light and dark mode both visually stable
'@

$nextSessionStarter = @'
SPRINT 8 NEXT SESSION STARTER
=============================
1. Verify /estate, /reference, and a detail page all return HTTP 200.
2. Check theme toggle on each page.
3. Commit the Sprint 8 Pillar 3C milestone.
'@

$remarksNotes = @'
# Sprint 8 Remarks and Manual Update Notes
Do not update manuals mid-refactor. Document only once the current frontend state is stable and confirmed working.
'@

$languageMapping = @'
# Sprint 8 Operator Language Mapping
Managed Disabled Accounts -> Disabled User Accounts
No Tracked Jira Site Access -> Users Without Jira Access
Inactive Without Site Access -> Inactive Users (No Access)
Bitbucket Only / No Tracked Jira -> Bitbucket-only Users
Trend lookback -> Snapshot history depth
'@

Write-Step "Writing frontend files"
Write-Utf8NoBom "templates\estate.html" $estateHtml
Write-Utf8NoBom "templates\reference.html" $referenceHtml
Write-Utf8NoBom "templates\detail_list.html" $detailHtml
Write-Utf8NoBom "static\css\estate.css" $estateCss
Write-Utf8NoBom "static\css\reference.css" $referenceCss

Write-Step "Writing Sprint 8 docs"
Write-Utf8NoBom "docs\sprints\SPRINT_8_PROGRESS_ARCHIVE.md" $progressArchive
Write-Utf8NoBom "docs\sprints\SPRINT_8_NEXT_SESSION_STARTER.txt" $nextSessionStarter
Write-Utf8NoBom "docs\manuals\SPRINT_8_REMARKS_AND_MANUAL_UPDATE_NOTES.md" $remarksNotes
Write-Utf8NoBom "docs\sprints\SPRINT_8_OPERATOR_LANGUAGE_MAPPING.md" $languageMapping

Write-Step "Verification checklist"
Write-Host "Run these next:" -ForegroundColor Yellow
Write-Host "  Invoke-WebRequest http://127.0.0.1:5000/estate -TimeoutSec 5 -UseBasicParsing | Select-Object StatusCode"
Write-Host "  Invoke-WebRequest http://127.0.0.1:5000/reference -TimeoutSec 5 -UseBasicParsing | Select-Object StatusCode"
Write-Host "  Invoke-WebRequest http://127.0.0.1:5000/detail/change::summary -TimeoutSec 5 -UseBasicParsing | Select-Object StatusCode"
Write-Host "  Invoke-RestMethod http://127.0.0.1:5000/api/source-state -TimeoutSec 5 | Select-Object source_mode, auto_sync_active"

Write-Step "Suggested commit"
Write-Host 'git add templates\estate.html templates\reference.html templates\detail_list.html static\css\estate.css static\css\reference.css docs\sprints\SPRINT_8_PROGRESS_ARCHIVE.md docs\sprints\SPRINT_8_NEXT_SESSION_STARTER.txt docs\sprints\SPRINT_8_OPERATOR_LANGUAGE_MAPPING.md docs\manuals\SPRINT_8_REMARKS_AND_MANUAL_UPDATE_NOTES.md'
Write-Host 'git commit -m "Sprint 8 combined checkpoint: align estate/reference/detail pages and add Sprint 8 docs pack"'
Write-Host 'git push'

Write-Step "Complete"
Write-Host "Sprint 8 combined pack applied successfully." -ForegroundColor Green
