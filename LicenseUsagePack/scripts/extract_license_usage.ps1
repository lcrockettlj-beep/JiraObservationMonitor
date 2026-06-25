param(
    [string]$OutputDir
)

Write-Host "Extracting license usage..."

# ?? Replace with your real config if needed (same as previous pack)
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

        # Count product access (basic model)
        $jiraUsers = 0
        $confluenceUsers = 0

        foreach ($user in $users) {
            # Basic assumption: applicationRoles present
            if ($user.applicationRoles) {
                foreach ($role in $user.applicationRoles.items) {
                    if ($role.key -like "*jira*") {
                        $jiraUsers++
                    }
                    if ($role.key -like "*confluence*") {
                        $confluenceUsers++
                    }
                }
            }
        }

        $output = @{
            site = $siteName
            total_users = $users.Count
            jira_users = $jiraUsers
            confluence_users = $confluenceUsers
            generated = (Get-Date)
        }

        $filePath = Join-Path $OutputDir "$siteName-license.json"
        $output | ConvertTo-Json -Depth 5 | Set-Content $filePath

        Write-Host "OK: $siteName (Jira=$jiraUsers / Conf=$confluenceUsers)"

    } catch {
        Write-Host "FAIL: $siteName"
    }
}
