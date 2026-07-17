# Operator Startup and Demo Runbook v1

## Start JOM locally

```powershell
cd "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
python -m app.web
```

## Open workspaces

```text
Command Centre: http://127.0.0.1:5000/
Estate:         http://127.0.0.1:5000/estate
Admin:          http://127.0.0.1:5000/reference
Site example:   http://127.0.0.1:5000/site/gli-it-project
```

## Demo sequence

1. Command Centre: show estate health, alerts, discovery and AI operational brief.
2. Estate: show monitored/discovered estate position and open a site workspace from the right-hand panel.
3. Site Workspace: show single-site investigation and diagnostics.
4. Admin: show discovery governance, named access, runtime/source state and API connection visibility.
5. Reports: open `docs/executive_demo_reporting_v1/REPORTING_PACK_INDEX_V1.md`.

## Retained compatibility routes

Do not remove these during the current production candidate phase:

- `/api/data`
- `/api/source-state`
- `/api/site-registry`
