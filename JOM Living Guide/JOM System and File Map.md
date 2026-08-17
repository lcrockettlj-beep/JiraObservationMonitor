# The Jira Observation Monitor Guide

## How JOM Works, How It Is Built, and How Work Continues

**As-built baseline:** `main` at `29d1166b10da980da847f3ae8978e1191b24b8b9`
**Evidence date:** 14 August 2026
**Document status:** Living controlled guide

# Appendix A. Page and Owner Map

## Command Centre
- Visible page: `templates/home.html`
- Browser behaviour: `static/js/jom_command_centre_completion_v1.js`
- Visual styling: `static/css/jom_command_centre_completion_v1.css`
- Page address: `/home`
- Main information address: `/api/workspace/command-centre`

## Estate
- Visible page: `templates/estate.html`
- Browser behaviour: `static/js/jom_estate_lifecycle_v1.js`
- Visual styling: `static/css/jom_estate_lifecycle_v1.css`
- Page address: `/estate`
- Main information address: `/api/workspace/estate`

## Site Review
- Visible page: `templates/site_review.html`
- Browser behaviour: `static/js/jom_site_review_v1.js`
- Visual styling: `static/css/jom_site_review_v1.css`
- Page address: `/estate/review/<site_key>`
- Main information address: `/api/site-review/<site_key>`

## Site Workspace
- Visible page: `templates/site_workspace.html`
- Browser behaviour: `static/js/jom_site_workspace_shell_v1.js`
- Visual styling: `static/css/jom_site_workspace_shell_v1.css`
- Page address: `/site-workspace/<site_key>`
- Main information address: `/api/workspace/product-users`

## Licensing & Billing
- Visible page: `templates/admin_licensing_billing.html`
- Browser behaviour: `static/js/jom_admin_licensing_billing_v1.js`
- Visual styling: `static/css/jom_admin_licensing_billing_v1.css`
- Page address: `/admin/licensing-billing`
- Main information address: `/api/admin/licensing-billing`

## Monitoring
- Visible page: `templates/admin_monitoring.html`
- Browser behaviour: `static/js/jom_admin_monitoring_v1.js`
- Visual styling: `static/css/jom_admin_monitoring_v1.css`
- Page address: `/admin/monitoring`
- Main information address: `/api/admin/monitoring`

## Users & Access
- Visible page: `templates/admin_users_access.html`
- Browser behaviour: `static/js/jom_admin_users_access_v1.js`
- Visual styling: `static/css/jom_admin_users_access_v1.css`
- Page address: `/admin/users-access`
- Main information address: `/api/admin/users-access`

## System Configuration
- Visible page: `templates/admin_system_configuration.html`
- Browser behaviour: `static/js/jom_admin_system_configuration_v1.js`
- Visual styling: `static/css/jom_admin_system_configuration_v1.css`
- Page address: `/admin/system-configuration`
- Main information address: `/api/admin/system-configuration`

## Executive Report
- Visible page: `templates/executive_report.html`
- Browser behaviour: `static/js/jom_executive_report_v1.js`
- Visual styling: `static/css/jom_executive_report_v1.css`
- Page address: `/executive-report`
- Main information address: `/api/reporting/executive-report`

## Estate Report
- Visible page: `templates/estate_report.html`
- Browser behaviour: `static/js/jom_estate_report_v1.js`
- Visual styling: `static/css/jom_estate_report_v1.css`
- Page address: `/estate-report`
- Main information address: `/api/reporting/estate-report`

## Governance Report
- Visible page: `templates/governance_report.html`
- Browser behaviour: `static/js/jom_governance_report_v1.js`
- Visual styling: `static/css/jom_governance_report_v1.css`
- Page address: `/reports/governance`
- Main information address: `/api/reporting/governance-report`

## Runtime Status
- Visible page: `templates/runtime_status.html`
- Browser behaviour: `No dedicated page script proven`
- Visual styling: `Shared visual styles`
- Page address: `/runtime-status`
- Main information address: `/runtime/status`

## Source Health
- Visible page: `templates/source_health.html`
- Browser behaviour: `No dedicated page script proven`
- Visual styling: `Shared visual styles`
- Page address: `/source-health`
- Main information address: `/api/source-state`

### Estate Configuration
- Visible page: `templates/admin_estate_configuration.html`
- Browser behaviour: `static/js/jom_admin_estate_configuration_v1.js`
- Visual styling: `static/css/jom_admin_estate_configuration_v1.css`
- Page address: `/admin/estate-configuration`
- Main information address: `/api/admin/estate-configuration`
- Backend owner: `app/web.py`
- Validation owner: `scripts/validate_estate_configuration_v1.py`
- Authority state: live validated, review status because seven authority gaps remain

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
