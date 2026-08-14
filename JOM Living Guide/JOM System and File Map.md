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
