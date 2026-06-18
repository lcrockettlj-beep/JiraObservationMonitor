UI Mapping + 600-Second Refresh Pack
====================================

Purpose:
1. Fix API/UI mapping so admin-enriched runtime data surfaces correctly in the existing runtime contract.
2. Add a safe backend refresh loop every 600 seconds.

Files in this pack:
- runtime_source_adapter.py -> place in backend/runtime_source_adapter.py
- run_api_runtime_refresh_600s.ps1 -> place in project root
- REFRESH_600S_NOTES.txt -> place in project root

Keep as-is:
- current auth.py
- current web.py
- current admin_api_client.py
- current admin_api_enrichment.py

What this pack changes:
- latest_run_admin_enriched.json remains the preferred runtime source.
- users_row_count now maps from admin_enrichment.users when present.
- managed_row_count now maps from managed claimStatus rows in admin_enrichment.users.
- estate totals continue to prefer admin-enriched values.
- users_export_breakdown is populated from admin_enrichment.summary.
- adds a backend refresh loop that runs every 600 seconds.

Install order:
1. Replace backend/runtime_source_adapter.py
2. Add run_api_runtime_refresh_600s.ps1 to project root
3. Add REFRESH_600S_NOTES.txt to project root

Run order:
1. PowerShell window A:
   powershell -ExecutionPolicy Bypass -File .\run_api_runtime_refresh_600s.ps1
2. PowerShell window B:
   python web.py
3. Check:
   http://127.0.0.1:5000/api/source-state

Expected result:
- source_file = latest_run_admin_enriched.json
- users_row_count > 0
- managed_row_count > 0
- source_mode = runtime
