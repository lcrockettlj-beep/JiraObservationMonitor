# ============================================================
# test_multi_user_poc.ps1 — Run the Phase 2 POC Demo
# ============================================================
#
# Convenience wrapper for the Phase 2 POC demo.
# Demonstrates the multi-user authentication flow using in-memory
# mocks. Makes no network calls and changes no persistent state.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\test_multi_user_poc.ps1
#
# Or simply:
#   .\scripts\test_multi_user_poc.ps1
# ============================================================

$ProjectRoot = "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
Set-Location $ProjectRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  JOM Phase 2 POC Demo Wrapper" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  This script runs an in-memory simulation of the Phase 2"
Write-Host "  multi-user authentication flow."
Write-Host ""
Write-Host "  - No network calls" -ForegroundColor Green
Write-Host "  - No persistent state changes" -ForegroundColor Green
Write-Host "  - No effect on Phase 1 operation" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Enter to continue, or Ctrl+C to cancel." -ForegroundColor Yellow
Read-Host

python scripts\poc_demo.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Demo complete." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  See docs\architecture\MULTI_USER_ARCHITECTURE.md for"
Write-Host "  the full Phase 2 architecture this demo simulates."
Write-Host ""
