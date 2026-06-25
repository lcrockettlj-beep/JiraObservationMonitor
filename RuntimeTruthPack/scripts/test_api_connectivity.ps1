Write-Host "Checking API..."

if (-not $global:headers) {
    Write-Host "WARN: headers not set"
}

$sites = @(
    "https://your-site-1.atlassian.net",
    "https://your-site-2.atlassian.net",
    "https://your-site-3.atlassian.net"
)

foreach ($site in $sites) {
    try {
        Invoke-RestMethod "$site/rest/api/3/serverInfo" -Headers $global:headers | Out-Null
        Write-Host "OK: $site"
    } catch {
        Write-Host "FAIL: $site"
    }
}
