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
## Collector Inventory Authority Audit, 17 August 2026

**Evidence source:** `JOM_Collector_Audit.txt`
**Repository baseline:** `main` at `0c2e865fb1c5bed3dc68468aa5c3736f7e5621e2`
**Workstream:** Marketplace App Authority Build

The repository audit confirmed that JOM already contains a substantial authority collector estate. New collector work must first be checked against this inventory to prevent duplicate implementation.

### Confirmed collector and authority owners

- Organisation discovery: `app/builders/organisation_discovery.py` -> `runtime/data/organisation_discovery.json`.
- Directory users, account state, MFA and platform roles: `app/access/admin_named_access_endpoint_probe.py` -> `runtime/data/admin_directory_users.json`.
- Directory group expansion, memberships and group role assignments: `app/access/collect_admin_group_expansion.py` -> `runtime/data/admin_group_expansion.json`.
- Jira product access: `app/builders/estate_product_access.py` -> `runtime/data/estate_product_access.json`.
- Site resource and ARI authority: `app/builders/estate_resource_authority.py` -> `runtime/data/estate_site_resource_mapping_v1.json` and `runtime/data/estate_resource_authority_refresh_status_v1.json`.
- Monitored product authority: `app/builders/estate_monitored_product_authority.py` -> `runtime/data/estate_monitored_product_authority_v1.json`.
- Administrative ownership: `app/builders/estate_admin_contacts.py` -> `runtime/data/estate_admin_contacts_v1.json`.
- Named site access: `app/builders/named_site_access_authority_v1.py` -> `runtime/data/named_site_access_authority_v1.json`.
- Named user display identity: `app/builders/named_user_display_identity_v1.py` -> `runtime/data/named_user_display_identity_v1.json`.
- Verified active Jira users: `app/builders/verified_active_jira_users_v1.py` -> `runtime/data/verified_active_jira_users_v1.json`.
- Users & Access actionable drill-downs: `app/builders/users_access_actionable_drilldown_v1.py` -> `runtime/data/users_access_actionable_drilldown_v1.json`.
- Consolidated Admin truth: `app/builders/admin_truth_layer_v2.py` -> `runtime/data/admin_truth_v2.json`.
- Runtime orchestration: `app/runtime/admin_enriched_chain.py`.

### Current Marketplace Apps boundary

Marketplace App discovery and limitation owners exist, but no supported non-browser installed-app enumeration collector has passed the publication gates. `runtime/data/estate_marketplace_app_authority_v1.json` therefore remains the truthful unavailable authority. The Marketplace App Authority Build remains the current workstream. The existing Collector Inventory must be reused before creating a new owner.

### Continuation rule

Do not redesign organisation, directory user, group, product access, resource, ownership, named-access, display-identity, active-user or actionable-drilldown collectors without evidence that the current owner is unsuitable. Continue the Marketplace App Authority Build from the existing discovery audits and limitation contract. Build a new collector only through a supported source, explicit contract, site-binding validation, completeness gates and safe publication approval.

<!-- JOM_FOUNDATION_RECOVERY_BOOKSYNC_V1_START -->

## Foundation Recovery Audit and Current Build Reality

**Recorded:** 18 August 2026
**Repository baseline:** `main` at `3723d19`
**Current workstream:** Foundation Recovery Audit

### Why this record exists

A platform-wide visual and runtime review established that earlier completion language often described authority or page construction, not dependable daily operation. JOM is required to be a live, read-only operational console. A collector or page is not complete merely because it exists or worked on the day it was built.

The current build is centred on the Admin workstream. Pages outside Admin were inherited from an earlier build and must be treated as placeholders or legacy migration candidates until they are separately audited, rebuilt against the current authority-first architecture, automatically refreshed, live-tested and accepted.

### Completion definitions

- **Placeholder:** A visible shell or framework without a completed current-authority implementation.
- **Legacy placeholder:** A page inherited from an earlier build that may render data but is not accepted as current operational architecture.
- **Authority complete:** An authenticated source, collector or builder, and runtime contract exist. This does not prove daily operational completion.
- **Operational:** Authority, collection, runtime contract, automatic refresh, presentation, drill-downs and end-to-end operator workflow all work with current evidence.
- **Complete:** Operational, validated, accepted by Luke, documented through BOOKSYNC, committed and pushed.

### Non-negotiable live-operation rule

A page is not complete because it renders. A page may be marked complete only when all of the following are proven:

1. Authority exists.
2. A collector or builder exists.
3. A defined runtime contract exists.
4. A refresh path exists.
5. Normal refresh is automatic and does not depend on Luke remembering to run a script.
6. The page presents the current contract correctly.
7. Every offered drill-down and action works.
8. Timestamps are trustworthy and distinguish live refresh from configuration change.
9. The end-to-end operator workflow works on an ordinary day, not only on build day.
10. Validation, user acceptance, BOOKSYNC, commit and push are complete.

If a live value cannot be refreshed automatically, JOM must report it as unavailable or clearly classify it as configuration authority. Stale data must not be presented as current truth.

### Current completion matrix

#### Current Admin architecture

- **Estate Configuration:** Authority implemented; operational review reopened because source refresh behaviour is inconsistent and must become automatic.
- **Users & Access:** Authority implemented; operationally incomplete because actionable drill-down buttons currently open an unavailable-authority result.
- **Monitoring:** Current Admin implementation; automatic-refresh and source-health claims require Foundation Recovery validation.
- **Licensing & Billing:** Current Admin implementation; product-access authority exists while commercial billing remains explicitly unavailable.
- **System Configuration:** Current Admin implementation; refresh-state interpretation and automatic update behaviour require Foundation Recovery validation.
- **Discovery:** Placeholder within Admin. The visible framework is not an accepted operational discovery implementation.

#### Non-Admin pages from the earlier build

- **Command Centre:** Legacy placeholder.
- **Estate:** Legacy placeholder.
- **Site Workspace:** Legacy placeholder shell. Site selection works, but Projects, Marketplace Apps and Automation are not connected and the selected-site body is not an accepted current implementation.
- **Executive Report:** Legacy placeholder.
- **Estate Report:** Legacy placeholder.
- **Governance Report:** Legacy placeholder.
- **Runtime Status:** Placeholder.
- **Source Health:** Placeholder.

No page in this group may be called operational until it is rebuilt or migrated and passes the full completion definition above.

### Open Foundation Recovery findings

#### FR-001: Users & Access drill-downs blocked

Buttons and routes exist, and `runtime/data/users_access_actionable_drilldown_v1.json` exists, but the displayed drill-down reports that freshness, privacy, population and safety gates were not all passed. The failing gate or gates must be identified from current runtime evidence. Buttons must not promise an operational drill-down while all results are blocked.

#### FR-002: Unified runtime refresh status missing

`app/runtime/runtime_sources_refresh.py` defines `runtime/data/runtime_refresh_status.json`, but that contract was absent during the 18 August 2026 audit. The orchestrator's execution, ownership and automatic scheduling are unproven.

#### FR-003: Refresh architecture inconsistent

Runtime contracts have materially different update times. Some participate in the current Admin chain, some are rebuilt only by specific owners, some are configuration or lifecycle decisions, and some are old or disconnected. Every displayed contract must be classified as automatically refreshed, configuration authority, unavailable, legacy or retired.

#### FR-004: Timestamp meaning is inconsistent

Pages currently place live collection timestamps, derived-authority timestamps and configuration-change timestamps together. UI labels must distinguish `Last refreshed`, `Last derived`, and `Last authority change` where applicable.

#### FR-005: Placeholder pages can be mistaken for current features

Discovery, Runtime Status, Source Health and the earlier non-Admin pages render visible frameworks. Rendering must not be interpreted as operational completion.

### Current authority and file ownership catalogue

- `app/web.py`: Primary Flask page and API route owner. Consumers must be audited by route before changes.
- `app/access/admin_named_access_endpoint_probe.py`: Collects organisation directory account, state, MFA and administrative-role evidence into `runtime/data/admin_directory_users.json`.
- `app/access/collect_admin_group_expansion.py`: Collects directory groups, memberships and group role assignments into `runtime/data/admin_group_expansion.json` with status in `runtime/data/admin_group_expansion_status.json`.
- `app/builders/admin_truth_layer_v2.py`: Builds consolidated Admin truth in `runtime/data/admin_truth_v2.json`.
- `app/builders/organisation_discovery.py`: Collects organisation authority into `runtime/data/organisation_discovery.json`; its automatic refresh path is not yet proven.
- `app/builders/estate_product_access.py`: Resolves OAuth authority and collects Jira application-role/product-access evidence into `runtime/data/estate_product_access.json` and `runtime/data/estate_access_truth.json`.
- `app/builders/product_access_sources.py`: Refresh wrapper for product-access contracts and `runtime/data/product_access_refresh_status.json`.
- `app/builders/estate_resource_authority.py`: Resolves monitored site Cloud IDs, resource mapping and administrative ownership; writes `runtime/data/estate_site_resource_mapping_v1.json`, `runtime/data/estate_admin_contacts_v1.json` and `runtime/data/estate_resource_authority_refresh_status_v1.json`.
- `app/builders/estate_admin_contacts.py`: Administrative ownership collection support used by resource authority.
- `app/builders/estate_monitored_product_authority.py`: Derives monitored-product authority into `runtime/data/estate_monitored_product_authority_v1.json`; automatic orchestration is not yet proven.
- `app/builders/estate_marketplace_app_authority.py`: Keeps Marketplace App authority truthfully unavailable in `runtime/data/estate_marketplace_app_authority_v1.json`; it is retained outside the Estate Configuration presentation.
- `app/builders/named_site_access_authority_v1.py`: Builds named site-access authority in `runtime/data/named_site_access_authority_v1.json`.
- `app/builders/named_user_display_identity_v1.py`: Builds privacy-approved display identity in `runtime/data/named_user_display_identity_v1.json`.
- `app/builders/users_access_actionable_drilldown_v1.py`: Builds actionable drill-down authority in `runtime/data/users_access_actionable_drilldown_v1.json`; current operational gates are failing and must be audited.
- `app/builders/verified_active_jira_users_v1.py`: Holds the verified-active-user authority attempt in `runtime/data/verified_active_jira_users_v1.json`; headline verified active users remain unavailable unless its gates pass.
- `app/registry/site_registry_runtime.py`: Registry lifecycle and approved-scope recovery owner. Commit `3723d19` aligned recovery authority to four approved monitored sites.
- `runtime/data/site_registry.json`: Current monitored-scope configuration/lifecycle authority. Its timestamp represents authority change, not necessarily a daily collection refresh.
- `app/runtime/admin_enriched_chain.py`: Current Admin-oriented runtime orchestration owner.
- `app/runtime/runtime_sources_refresh.py`: Separate runtime refresh orchestrator that expects `runtime/data/runtime_refresh_status.json`; its role and automatic execution require recovery audit.
- `app/runtime/runtime_data_paths.py`: Enforces `runtime/data` as the only active runtime read/write location.
- `scripts/audit_source_freshness.py`: Rebuilds freshness and reliability contracts.
- `runtime/data/source_freshness_audit.json`: Current freshness assessment output, not proof that every source is automatically refreshed.
- `runtime/data/source_reliability_status.json`: Current reliability assessment output, not proof that every source is automatically refreshed.

### Project Inventory discovery retained but deferred

A read-only live probe proved Jira project-search authority across all four monitored sites with HTTP 200 responses. Visible totals at probe time were 22, 9, 56 and 5, for 92 visible projects. Proven fields included project identity, type, style, simplified state, privacy state and category where supplied. Lead, archive state, activity, permission scheme and workflow scheme were not proven.

Project Inventory implementation is deferred until Foundation Recovery establishes dependable automatic refresh and repairs current drill-down defects. The probe totals must never be hard-coded or treated as permanent.

### Foundation Recovery workstream order

1. Build a complete page, route, runtime-contract, collector and refresh ownership matrix.
2. Audit and repair Users & Access drill-down gates.
3. Establish one dependable automatic refresh operating model for all live Admin authorities.
4. Classify configuration contracts separately from refreshable contracts.
5. Repair freshness and timestamp presentation.
6. Revalidate every current Admin page end to end.
7. Only after the Admin foundation is operationally accepted, resume new collectors such as Project Inventory.
8. Rebuild legacy and placeholder pages later as consumers of the completed current authority architecture.

### Cross-chat continuation rule

A new chat must not restart broad discovery or select a new feature from old assumptions. Start with:

1. `git status --short`
2. `git log -1 --oneline`
3. This Foundation Recovery record
4. The open finding list
5. The current owner files for the active finding

Do not call Command Centre, Estate, Site Workspace, Reports, Runtime Status or Source Health operational. Do not call an Admin page complete until automatic refresh and all offered drill-downs have been proven in normal operation. Do not repeat already recorded authority audits unless a relevant owner changed, a validator failed, or new live evidence contradicts this guide.

<!-- JOM_FOUNDATION_RECOVERY_BOOKSYNC_V1_END -->
