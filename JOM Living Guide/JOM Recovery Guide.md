# JOM Recovery Guide

After an interrupted session, first inspect branch, HEAD and working tree. Do not reapply packs blindly. Identify modified tracked files, untracked pack folders, transient logs and runtime drift. Restore unrelated runtime files only after confirming they are not the intended milestone. Re-run syntax and contract checks. Use the latest committed guide and Git history to locate the last complete milestone.

For a new conversation, provide the Quick Start section, current `git status --short`, latest commit, current workstream and relevant owner files. Broad repository re-audits should be avoided when the guide is current.

## Repository recovery checklist
- `git branch --show-current`
- `git log -1 --oneline`
- `git status --short`
- Separate intended owner changes from runtime drift.
- Remove extracted `_pack_` and `_audit_` folders after evidence is retained.
- Remove transient access logs before commit.
- Compile Python owners and run packaged validators.
- Run `git diff --check` before staging and `git diff --cached --check` after staging.

### Estate Configuration recovery point
If work is interrupted before commit, retain only the five Estate Configuration product owners and the BOOKSYNC documentation replacements. Restore unrelated runtime JSON drift and remove transient JSONL access logs before staging. Re-run `python scripts\validate_estate_configuration_v1.py`, `python -m py_compile app\web.py`, `git diff --check` and live contract validation before committing.

### Estate Configuration completion record, 17 August 2026
- Completion status: accepted after static, runtime, authority, privacy, consistency and visual validation.
- API authority: `jom-admin-estate-configuration-authority-v3` at `/api/admin/estate-configuration`.
- Page: `/admin/estate-configuration`; selected-site continuation: `/site-workspace/<site-key>`.
- Current estate evidence: 4 monitored sites, 2 unique monitored products, 6 proven site-product assignments and 100% product coverage.
- Current administrative ownership: 4 of 4 sites, 33 role-assignment rows and 100% coverage. Role assignments are not unique people.
- Marketplace Apps: unavailable through the current JOM integration. Browser-session Jira gateway candidates existed, but Admin Bearer returned HTTP 406 and OAuth Bearer returned HTTP 401 across the four-site endpoint audit. No app records or fabricated counts are published.
- Runtime status: `ok_with_limitations`; Marketplace Apps is the single non-blocking limitation; blocking actions: 0.
- Privacy boundary: no personal ownership records, email addresses, account IDs, directory IDs, resource identifiers, cloud IDs, credentials, headers or raw Connected Apps payloads are returned by the page contract.
- Validation owners: `scripts/validate_estate_configuration_v1.py`, `scripts/validate_estate_configuration_inventory_v3.py`, `scripts/validate_estate_configuration_ui_refinement_v1.py`, `scripts/validate_estate_resource_ari_correction_v1.py`, `scripts/validate_monitored_product_authority_v1.py`, `scripts/validate_marketplace_app_limitation_authority_v1.py`.
- Commit gate: install these BOOKSYNC owners, validate product and documentation together, inspect staged scope, then commit and push.
- Next workstream: choose the next incomplete Admin page only after this milestone is clean and pushed. Discovery remains parked unless explicitly selected.
