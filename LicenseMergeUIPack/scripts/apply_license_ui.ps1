param([string]$ProjectRoot)

# HOME
$homeFile = Join-Path $ProjectRoot "ui\home.js"

$content = Get-Content $homeFile -Raw
$content = $content -replace '</div><!-- END SUMMARY -->', @"
<div class=\"jom-card\">
  <h3>Jira Licenses</h3>
  <p id=\"jiraLicenses\">0</p>
</div>
<div class=\"jom-card\">
  <h3>Confluence Licenses</h3>
  <p id=\"confLicenses\">0</p>
</div>
</div><!-- END SUMMARY -->
"@
Set-Content $homeFile $content

# ESTATE
$estateFile = Join-Path $ProjectRoot "ui\estate.js"

$content = Get-Content $estateFile -Raw
$content = $content -replace '</div><!-- END SUMMARY -->', @"
<div class=\"jom-card\">
  <h3>Jira Licenses</h3>
  <p id=\"jiraLicensesEstate\">0</p>
</div>
<div class=\"jom-card\">
  <h3>Confluence Licenses</h3>
  <p id=\"confLicensesEstate\">0</p>
</div>
</div><!-- END SUMMARY -->
"@
Set-Content $estateFile $content

Write-Host "UI Updated"
