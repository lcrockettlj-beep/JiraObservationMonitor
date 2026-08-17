# JOM Progress and Improvements

## Completed or substantially advanced
- Static truth removal and runtime path alignment.
- Command Centre and Estate authority alignment.
- Site Review lifecycle and Site Workspace shell.
- Monitoring authority and refresh alignment.
- Users & Access account, role, footprint, named-user and actionable drill-down authority.
- Executive, Estate and Governance report authority views.

## Open or authority-blocked
- Not-invited user authority.
- Commercial billing authority.
- Phase 2 multi-user authentication and organisation administrator enforcement.
- Page-by-page release acceptance and broader typography consistency.
- Estate Configuration review and later Site Workspace depth.

### Estate Configuration authority completed
- Replaced the static shell with a dedicated runtime-backed authority page.
- Added a dedicated read-only API contract.
- Added site-level tenant identity, resource mapping and ownership coverage.
- Added privacy-safe role-assignment totals.
- Added source state and evidence timestamps.
- Preserved business classification, criticality, region, business unit and tags as unavailable.
- Live validated 4 sites, 4 monitored sites, 100% tenant identity, 75% resource mapping, 75% ownership coverage, 97 assignments, 7 gaps and 0 failed sources.

### Current next step
- Perform the Estate Configuration BOOKSYNC commit.
- After the milestone is clean and pushed, continue with the next incomplete Admin authority area using the same audit-first workflow.

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

## 2026-08-17 16:41:25 +01:00 - Estate Configuration Marketplace presentation removed

### Decision

Marketplace App inventory has been removed from the Estate Configuration presentation because no supported non-browser authority was proven.

### Evidence

- Four monitored sites tested.
- Sixteen expected probes completed.
- Zero probes succeeded.
- Eight direct-site UPM probes returned HTTP 406.
- Eight scoped Jira API probes returned HTTP 401.
- Marketplace App installation authority remains unproven.
- Marketplace App inventory remains unsafe to publish.
- No zero or inferred app values are displayed.

### Implementation

Removed Marketplace Apps from:

- Estate Configuration headline metrics.
- Site configuration table.
- Authority status rail.
- Operational actions.
- Authority source cards.
- Estate Configuration API presentation contract.

Retained:

- Marketplace limitation builder.
- Marketplace runtime limitation contract.
- Audit and discovery evidence.
- Future authority requirements.

Estate Configuration now presents only:

- Monitored sites.
- Monitored products.
- Administrative ownership coverage.
- Configuration actions.
- Site registry, monitored-product and administrative-ownership sources.

### Validation

- Marketplace UI removal validator: PASS.
- Estate Configuration lifecycle validator: PASS.
- Live API response: HTTP 200.
- Live page visual validation: PASS.
- Marketplace presentation negative-reference audit: PASS.
- Git whitespace validation: PASS.

### Authentication cleanup

- Temporary Marketplace service-account token revoked.
- Temporary Marketplace service-account settings removed from .env.
- Established svc-atlassian-jom service identity retained.
