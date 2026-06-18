API-Only Runtime Pack
=====================

Purpose:
Move the monitor fully into API-driven runtime flow without relying on CSV truth.

Files in this pack:
- admin_api_client.py -> project root
- admin_api_enrichment.py -> project root
- runtime_source_adapter.py -> backend/runtime_source_adapter.py
- run_api_runtime_cycle.ps1 -> project root
- preview_static_cleanup.ps1 -> project root
- API_ONLY_RUNTIME_PACK_README.txt -> project root

What this pack does:
1. Uses your working Jira OAuth 3LO auth for product/site runtime collection (via your existing collector/auth flow).
2. Uses your working Atlassian Admin API key/org auth for org/user enrichment.
3. Writes:
   - latest_run.json            (collector output)
   - latest_run_admin_enriched.json
   - latest_run_admin_enriched_pretty.json
4. Makes the runtime adapter prefer the admin-enriched runtime file when present.

Recommended order:
1. Keep current auth.py and current working web.py.
2. Replace/add the files from this pack.
3. Run:
   powershell -ExecutionPolicy Bypass -File .\run_api_runtime_cycle.ps1
4. Start the web app:
   python web.py
5. Verify:
   http://127.0.0.1:5000/api/source-state

Expected source-state result after a successful cycle:
- source_mode = runtime
- source_file = latest_run_admin_enriched.json
- source_error = null

Optional validation:
- Use preview_static_cleanup.ps1 only as a review helper before deleting older CSV/static files.
