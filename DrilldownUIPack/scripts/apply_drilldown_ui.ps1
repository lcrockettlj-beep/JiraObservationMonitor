param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot
)

Write-Host "=== Drilldown UI Pack (Clean Apply) ===" -ForegroundColor Cyan

# =============================
# Inject Home Panel
# =============================
$homeFile = Join-Path $ProjectRoot "ui\home.js"

if (Test-Path $homeFile) {
    $content = Get-Content $homeFile -Raw

    if ($content -notmatch "disabledUsersHome") {
        $content = $content -replace '</div><!-- END SUMMARY -->', @"
<div class="jom-card critical" onclick="openDisabledDrilldown()">
    <h3>Disabled Users</h3>
    <p id="disabledUsersHome">0</p>
</div>
</div><!-- END SUMMARY -->
"@

        Set-Content $homeFile $content
        Write-Host "Home UI Injected" -ForegroundColor Green
    } else {
        Write-Host "Home already patched" -ForegroundColor Yellow
    }
}

# =============================
# Inject Estate Panel
# =============================
$estateFile = Join-Path $ProjectRoot "ui\estate.js"

if (Test-Path $estateFile) {
    $content = Get-Content $estateFile -Raw

    if ($content -notmatch "disabledUsersEstate") {
        $content = $content -replace '</div><!-- END SUMMARY -->', @"
<div class="jom-card critical" onclick="openDisabledDrilldown()">
    <h3>Disabled Users</h3>
    <p id="disabledUsersEstate">0</p>
</div>
</div><!-- END SUMMARY -->
"@

        Set-Content $estateFile $content
        Write-Host "Estate UI Injected" -ForegroundColor Green
    } else {
        Write-Host "Estate already patched" -ForegroundColor Yellow
    }
}

# =============================
# JS HANDLERS
# =============================
$commonJs = Join-Path $ProjectRoot "ui\common.js"

if (Test-Path $commonJs) {
    $jsContent = Get-Content $commonJs -Raw

    if ($jsContent -notmatch "updateDisabledCounts") {
        Add-Content $commonJs @"

function updateDisabledCounts(homeData, estateData) {
    if (document.getElementById("disabledUsersHome")) {
        document.getElementById("disabledUsersHome").innerText = homeData.disabled_users_total || 0;
    }

    if (document.getElementById("disabledUsersEstate")) {
        document.getElementById("disabledUsersEstate").innerText = estateData.disabled_users_total || 0;
    }
}

function openDisabledDrilldown() {
    window.location.href = "disabled-users.html";
}

"@
        Write-Host "JS handlers added" -ForegroundColor Green
    } else {
        Write-Host "JS already exists" -ForegroundColor Yellow
    }
}

# =============================
# CREATE DRILLDOWN PAGE
# =============================
$drilldownPath = Join-Path $ProjectRoot "ui\disabled-users.html"

@"
<!DOCTYPE html>
<html>
<head>
    <title>Disabled Users</title>
    <link rel=\"stylesheet\" href=\"styles.css\">
</head>
<body class=\"jom-theme\">

<h1>Disabled Users</h1>
<div id=\"disabledList\">Loading...</div>

<script>
fetch('../data/disabled_users_combined.json')
    .then(r => r.json())
    .then(data => {
        let html = '';

        data.forEach(site => {
            html += `<h2>${site.site}</h2>`;
            site.disabled_users.forEach(u => {
                html += `<div class="row">${u.displayName}</div>`;
            });
        });

        document.getElementById("disabledList").innerHTML = html;
    });
</script>

</body>
</html>
"@ | Set-Content $drilldownPath

Write-Host "Drilldown page created" -ForegroundColor Green

Write-Host "`n? Drilldown UI Pack Applied CLEANLY" -ForegroundColor Green
