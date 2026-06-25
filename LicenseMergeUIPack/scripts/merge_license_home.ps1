param([string]$ProjectRoot)

$homeFile   = Join-Path $ProjectRoot "data\home_summary.json"
$estateFile = Join-Path $ProjectRoot "data\estate_summary.json"

$home   = Get-Content $homeFile | ConvertFrom-Json
$estate = Get-Content $estateFile | ConvertFrom-Json

$home | Add-Member jira_users_total $estate.jira_users_total -Force
$home | Add-Member confluence_users_total $estate.confluence_users_total -Force

$home | ConvertTo-Json -Depth 10 | Set-Content $homeFile

Write-Host "Home Updated"
