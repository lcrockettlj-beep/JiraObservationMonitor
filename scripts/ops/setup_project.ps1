
# Run from the JiraObservationMonitor project root.
# This only creates folders if they do not already exist.

$templatesPath = Join-Path $PSScriptRoot "templates"
$staticPath = Join-Path $PSScriptRoot "static"

if (-not (Test-Path $templatesPath)) {
    New-Item -ItemType Directory -Path $templatesPath | Out-Null
}

if (-not (Test-Path $staticPath)) {
    New-Item -ItemType Directory -Path $staticPath | Out-Null
}

Write-Host "Templates folder:" $templatesPath
Write-Host "Static folder   :" $staticPath
Write-Host "Folder setup complete."
