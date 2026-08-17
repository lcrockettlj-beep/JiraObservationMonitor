param(
    [string]$ProjectRoot = ".",
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$project = (Resolve-Path $ProjectRoot).Path
if (-not $OutputRoot) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputRoot = Join-Path $project "JOM_PRODUCT_APP_AUTHORITY_AUDIT_$stamp"
}
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$repoFiles = Get-ChildItem (Join-Path $project "app"),(Join-Path $project "scripts"),(Join-Path $project "runtime\data") -Recurse -File -ErrorAction SilentlyContinue
$patterns = @(
    "marketplace", "installed app", "installed apps", "manage apps", "plugin", "plugins",
    "addon", "add-on", "upm", "entitlement", "offering", "app key", "app_key",
    "jira-service-management", "jira software", "confluence", "product_access",
    "resourceOwner", "accessible-resources", "workspaces"
)

$hits = foreach ($pattern in $patterns) {
    $repoFiles | Select-String -Pattern $pattern -SimpleMatch -ErrorAction SilentlyContinue | ForEach-Object {
        [pscustomobject]@{
            Pattern = $pattern
            Path = $_.Path.Substring($project.Length).TrimStart('\')
            LineNumber = $_.LineNumber
            Line = ($_.Line.Trim() -replace '(?i)(token|secret|api[_-]?key|authorization)\s*[:=]\s*[^,\s]+','$1=[REDACTED]')
        }
    }
}
$hits | Sort-Object Path,LineNumber,Pattern | Export-Csv (Join-Path $OutputRoot "repository_authority_references.csv") -NoTypeInformation -Encoding UTF8

$contracts = @()
Get-ChildItem (Join-Path $project "runtime\data") -File -Filter *.json -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $raw = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        $keys = @($raw.PSObject.Properties.Name)
        $text = Get-Content $_.FullName -Raw -Encoding UTF8
        $contracts += [pscustomobject]@{
            File = $_.Name
            Schema = $raw.schema
            Status = $raw.status
            GeneratedAt = $(if($raw.generated_at_utc){$raw.generated_at_utc}elseif($raw.updated_at_utc){$raw.updated_at_utc}else{$raw.generated_utc})
            TopLevelKeys = ($keys -join ", ")
            HasSites = ($keys -contains "sites")
            SiteCount = if ($raw.sites -is [array]) {@($raw.sites).Count} else {$null}
            ProductTerms = ([regex]::Matches($text,'(?i)jira-software|jira-service-management|confluence|bitbucket|compass|product')).Count
            AppTerms = ([regex]::Matches($text,'(?i)marketplace|installed.?app|plugin|addon|add-on|app_key|appKey')).Count
        }
    } catch {
        $contracts += [pscustomobject]@{File=$_.Name;Schema=$null;Status="invalid_json";GeneratedAt=$null;TopLevelKeys=$null;HasSites=$false;SiteCount=$null;ProductTerms=$null;AppTerms=$null}
    }
}
$contracts | Sort-Object File | Export-Csv (Join-Path $OutputRoot "runtime_contract_inventory.csv") -NoTypeInformation -Encoding UTF8

$siteProduct = @()
foreach ($name in @("estate_product_access.json","site_registry.json","estate_admin_site_inventory_v1.json","estate_site_resource_mapping_v1.json","organisation_discovery.json")) {
    $path = Join-Path $project "runtime\data\$name"
    if (-not (Test-Path $path)) { continue }
    try {
        $payload = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($row in @($payload.sites)) {
            if ($null -eq $row) { continue }
            $siteProduct += [pscustomobject]@{
                SourceFile = $name
                SiteKey = $(if($row.site_key){$row.site_key}elseif($row.key){$row.key}else{$row.name})
                Status = $row.status
                Product = $(if($row.product){$row.product}elseif($row.product_key){$row.product_key}else{$row.resource_type})
                JiraRoleCount = $row.jira_role_count
                ProductUserCount = $row.jira_product_user_count
                Fields = ($row.PSObject.Properties.Name -join ", ")
            }
        }
        foreach ($row in @($payload.mappings)) {
            if ($null -eq $row) { continue }
            $siteProduct += [pscustomobject]@{SourceFile=$name;SiteKey=$row.site_key;Status=$row.confidence;Product=$row.product;JiraRoleCount=$null;ProductUserCount=$null;Fields=($row.PSObject.Properties.Name -join ", ")}
        }
    } catch {}
}
$siteProduct | Sort-Object SiteKey,SourceFile,Product | Export-Csv (Join-Path $OutputRoot "site_product_evidence.csv") -NoTypeInformation -Encoding UTF8

$summary = [ordered]@{
    schema = "jom-product-marketplace-app-authority-audit-v1"
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    project_root = $project
    read_only = $true
    repository_reference_count = @($hits).Count
    runtime_contract_count = @($contracts).Count
    product_evidence_row_count = @($siteProduct).Count
    files = @(
        "repository_authority_references.csv",
        "runtime_contract_inventory.csv",
        "site_product_evidence.csv"
    )
    authority_questions = @(
        "Which contract proves the complete product inventory for every monitored site?",
        "Does product authority distinguish Jira Software, Jira Service Management and Confluence?",
        "Which authenticated source, if any, proves Marketplace app installation by site?",
        "Can app identity, vendor, enabled state and licensing be proven separately?",
        "Which missing capabilities require a new collector and runtime contract?"
    )
}
$summary | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $OutputRoot "audit_summary.json") -Encoding UTF8

$readme = @"
# JOM Product and Marketplace App Authority Audit

This audit is read-only. It does not call live endpoints, modify runtime contracts, or infer product/app inventory.

## Outputs
- repository_authority_references.csv
- runtime_contract_inventory.csv
- site_product_evidence.csv
- audit_summary.json

## Truth rule
A product or Marketplace app is publishable only after a real authenticated source, collector, runtime contract and validation gates exist. Missing authority remains unavailable.
"@
$readme | Set-Content (Join-Path $OutputRoot "README.md") -Encoding UTF8
Compress-Archive -Path (Join-Path $OutputRoot "*") -DestinationPath ($OutputRoot + ".zip") -Force
Write-Host "AUDIT_DIR=$OutputRoot"
Write-Host "AUDIT_ZIP=$OutputRoot.zip"

