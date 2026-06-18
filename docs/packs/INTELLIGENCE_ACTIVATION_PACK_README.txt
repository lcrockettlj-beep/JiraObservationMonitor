Intelligence Activation Pack
===========================

Purpose:
Add real operational intelligence on top of latest_run_alerted.json.

Files:
- intelligence_rules_engine.py -> project root
- run_intelligence_rules_once.ps1 -> project root
- INTELLIGENCE_ACTIVATION_PACK_README.txt -> project root

What it adds:
- latest_run_intelligence.json
- latest_run_intelligence_pretty.json
- intelligence_summary with:
  - estate_risk_score
  - top_intelligence_risks_count
  - sites_with_risks_count
  - operational_posture
  - analysed_sites_count
  - top_risks
- intelligence_watchlist rows
- drilldowns:
  - intelligence::summary
  - intelligence::watchlist

Recommended one-off test:
1. powershell -ExecutionPolicy Bypass -File .\run_intelligence_rules_once.ps1
2. python web.py
3. Check / or /api/data
