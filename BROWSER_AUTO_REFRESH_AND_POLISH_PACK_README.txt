Browser Auto-Refresh + Dashboard Polish Pack
===========================================

Purpose:
- add browser auto-refresh every 600 seconds
- add a lightweight Live Runtime status badge
- avoid risky backend changes
- preserve your current working auth/runtime pipeline

Files in this pack:
- dashboard_refresh.js -> place in static/js/dashboard_refresh.js
- apply_browser_refresh_pack.ps1 -> place in project root
- validate_browser_refresh_pack.ps1 -> place in project root
- BROWSER_AUTO_REFRESH_AND_POLISH_PACK_README.txt -> place in project root

What this pack does:
1. Adds a browser-side auto-refresh timer (600 seconds)
2. Polls /api/source-state every 60 seconds for health/source info
3. Displays a Live Runtime badge with:
   - source file
   - source status / sites count
   - last check time
   - countdown timer
   - pause/resume button
   - refresh now button
4. Safely patches templates to include the new JavaScript without replacing your UI files

Install order:
1. Put dashboard_refresh.js into static/js/
2. Put the two PowerShell scripts and this readme into project root
3. Run:
   powershell -ExecutionPolicy Bypass -File .\apply_browser_refresh_pack.ps1
4. Validate:
   powershell -ExecutionPolicy Bypass -File .\validate_browser_refresh_pack.ps1
5. Run the website:
   python web.py

Recommended run model:
- Window A: powershell -ExecutionPolicy Bypass -File .\run_api_runtime_refresh_600s.ps1
- Window B: python web.py
- Browser: open http://127.0.0.1:5000/

Expected result:
- a Live Runtime badge appears in the bottom-right corner
- the page auto-refreshes every 600 seconds unless paused
- the badge shows source file and source-state health
