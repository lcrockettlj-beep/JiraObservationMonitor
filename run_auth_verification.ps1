$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\Luke_C\Desktop\JiraObservationMonitor'
Set-Location $ProjectRoot

Write-Host "Running Atlassian auth verification..." -ForegroundColor Cyan
python .\auth_verification.py

Write-Host "" 
Write-Host "If the script succeeded, opening the text report..." -ForegroundColor Green
if (Test-Path .\auth_verification_report.txt) {
    notepad .\auth_verification_report.txt
} else {
    Write-Host "Report file not found." -ForegroundColor Yellow
}
