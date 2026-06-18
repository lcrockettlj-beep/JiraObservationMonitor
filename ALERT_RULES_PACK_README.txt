Alert Rules Pack
================

Purpose:
- activate explicit alert rules on top of the admin-enriched runtime payload
- produce latest_run_alerted.json as the preferred runtime source
- drive runtime badge glow/pulse from real conditions instead of placeholder state
- expose alert drilldowns in /api/data

Files in this pack:
- alert_rules_engine.py -> project root
- runtime_source_adapter.py -> backend/runtime_source_adapter.py
- run_api_runtime_refresh_600s.ps1 -> project root (updated)
- run_alert_rules_once.ps1 -> project root
- ALERT_RULES_PACK_README.txt -> project root

What it does:
1. Reads latest_run_admin_enriched.json
2. Applies alert rules for:
   - managed disabled accounts
   - MFA disabled accounts
   - accounts not in userbase
   - zero users / zero sites
   - site status warnings/critical
   - unresolved issue thresholds
3. Writes:
   - latest_run_alerted.json
   - latest_run_alerted_pretty.json
4. runtime_source_adapter.py prefers latest_run_alerted.json
5. /api/data exposes:
   - runtime_alerts
   - critical_sites
   - warning_sites
   - intelligence_summary.top_risks
   - alert drilldowns: alert::critical and alert::warning

Install order:
1. Put alert_rules_engine.py in project root
2. Replace backend/runtime_source_adapter.py
3. Replace run_api_runtime_refresh_600s.ps1 in project root
4. Add run_alert_rules_once.ps1 and this readme to project root

Run options:
A. One-off test:
   powershell -ExecutionPolicy Bypass -File .\run_alert_rules_once.ps1

B. Full live loop:
   powershell -ExecutionPolicy Bypass -File .\run_api_runtime_refresh_600s.ps1

Expected result:
- source_file becomes latest_run_alerted.json after the alert rules run
- runtime widget health becomes warning/critical when rule conditions are met
- /api/data exposes alert drilldowns and alert summary
