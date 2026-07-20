# Export and Reporting Implementation v1

This implementation adds source-backed HTML, JSON and CSV report endpoints and UI report actions for Command Centre, Estate, Admin and Site Workspace.

## Endpoints

- `/reports/generated/executive/html|json|csv`
- `/reports/generated/estate/html|json|csv`
- `/reports/generated/admin/html|json|csv`
- `/reports/generated/site/<site-key>/html|json|csv`

## Safety

No backend source contracts are changed. Retained `/api` routes remain available.
