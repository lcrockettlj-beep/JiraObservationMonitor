Auth Verification Pack
======================

Purpose:
Verify your Atlassian auth setup from the command line without bouncing around the website.

Files in this pack:
- auth_verification.py   -> place in project root
- run_auth_verification.ps1 -> place in project root
- AUTH_VERIFICATION_PACK_README.txt -> place in project root

What it checks:
1. Jira / OAuth 3LO side
   - .env config present
   - tokens.json present
   - access token / refresh token presence
   - token expiry state
   - accessible Jira resources via auth.get_accessible_jira_resources()

2. Admin API side
   - ATLASSIAN_ADMIN_API_KEY present
   - ATLASSIAN_ADMIN_ORG_ID present (if supplied)
   - admin org listing via auth.get_admin_orgs()

What it writes:
- auth_verification_report.json
- auth_verification_report.txt

Recommended use:
1. Keep your current auth.py as-is.
2. Put these files in project root.
3. Run:
   powershell -ExecutionPolicy Bypass -File .\run_auth_verification.ps1

If OAuth resources are not OK:
- run: python auth.py token
- if needed, run: python auth.py login

If Admin orgs are not OK:
- verify .env contains:
  ATLASSIAN_ADMIN_API_KEY=...
  ATLASSIAN_ADMIN_ORG_ID=...   (recommended)
- run: python auth.py admin-orgs
