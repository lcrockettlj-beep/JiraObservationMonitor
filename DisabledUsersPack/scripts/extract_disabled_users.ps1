param(
    [string]$OutputDir
)

Write-Host "Extracting disabled users..."

# ?? REPLACE WITH YOUR REAL SITE CONFIG OR LOAD FROM CONFIG FILE
$sites = @(
    @{ name = "site1"; url = "https://your-site-1.atlassian.net" },
    @{ name = "site2"; url = "https://your-site-2.atlassian.net" },
    @{ name = "site3"; url = "https://your-site-3.atlassian.net" }
)

foreach ($site in $sites) {
    $siteName = $site.name
    $baseUrl  = $site.url

    Write-Host "Processing $siteName..."

    try {
        $users = @()
        $start = 0
        $max   = 50

        do {
            $response = Invoke-RestMethod `
                -Uri "$baseUrl/rest/api/3/users/search?startAt=$start&maxResults=$max" `
                -Headers $global:headers

            $users += $response
            $start += $max

        } while ($response.Count -eq $max)

        $disabled = $users | Where-Object { $_.active -eq $false }

        $output = @{
            site              = $siteName
            total_users       = $users.Count
            disabled_count    = $disabled.Count
            disabled_users    = $disabled | Select-Object displayName, accountId
            generated         = (Get-Date)
        }

        $filePath = Join-Path $OutputDir "$siteName-disabled.json"
        $output | ConvertTo-Json -Depth 5 | Set-Content $filePath

        Write-Host "OK: $siteName ($($disabled.Count) disabled)"

    } catch {
        Write-Host "FAIL: $siteName"
    }
}
