param([string]$ProjectRoot)

$licenseDir = Join-Path $ProjectRoot "LicenseUsagePack\output"
$estateFile = Join-Path $ProjectRoot "data\estate_summary.json"

$totalJira = 0
$totalConf = 0

Get-ChildItem $licenseDir -Filter *.json | ForEach-Object {
    $data = Get-Content $_.FullName | ConvertFrom-Json
    $totalJira += $data.jira_users
    $totalConf += $data.confluence_users
}

$estate = Get-Content $estateFile | ConvertFrom-Json

$estate | Add-Member jira_users_total $totalJira -Force
$estate | Add-Member confluence_users_total $totalConf -Force

$estate | ConvertTo-Json -Depth 10 | Set-Content $estateFile

Write-Host "Estate Updated (Jira=$totalJira / Conf=$totalConf)"
