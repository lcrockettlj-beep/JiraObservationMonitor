# JOM Operator Quick Start

## Start JOM
```powershell
cd "C:\Users\Luke_C\Desktop\JiraObservationMonitor"
python -m app.web
```

## Open Workspaces
- Command Centre: `http://127.0.0.1:5000/`
- Estate: `http://127.0.0.1:5000/estate`
- Admin: `http://127.0.0.1:5000/reference`
- Site Workspace example: `http://127.0.0.1:5000/site/gli-it-project`

## Main Operator Flow
1. Open Command Centre.
2. Check readiness strip, alert count, discovery pressure and estate health.
3. Open Estate to review sites and select a site.
4. Use the right-hand panel to open the Site Workspace.
5. Open Admin for discovery, named access, runtime, source state and governance summary.

## Safety Model
JOM currently operates as a read-only operational intelligence console. Data is displayed from runtime and API-derived sources; UI components should not invent values.
