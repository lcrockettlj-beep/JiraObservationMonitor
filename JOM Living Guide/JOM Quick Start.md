# JOM Quick Start

Jira Observation Monitor (JOM) is a read-only operational console for observing an Atlassian estate through authenticated and runtime-backed authority. This guide records the system as built at branch `main` and commit `29d1166b10da980da847f3ae8978e1191b24b8b9` on 14 August 2026. The repository evidence identifies 184 tracked paths, 67 Python files, 34 HTML templates, 14 JavaScript files and 14 CSS files.

The defining engineering principle is truth before appearance. JOM must not invent a value merely to complete a dashboard. When evidence is absent, the correct output is unavailable. The guide is both a product explanation for non-technical readers and an owner reference for technical maintenance.

## Rules
- No assumptions as truth. If runtime or authenticated authority cannot prove a value, report it as unavailable.
- Do not present placeholders, estimates, screenshots, demonstrations, or stale snapshots as facts.
- User-facing truth must follow the live chain: page, browser code, API route, runtime contract, collector or builder, authenticated Atlassian authority.
- Audit the active owner, route, source and current file before making changes.
- Use single-owner implementation. No patch stacking, wrappers, sidecars, duplicate active pages or hidden overlays.
- Use exact user-provided paths and filenames.
- Deliver complete downloadable packs with extract, install, validate, clean, stage, commit and push workflow.
- Remove temporary packs and transient runtime logs before commit.
- BOOKSYNC is the documentation update gate before every Git save milestone.

## Resume safely
1. Open repository root.
2. Run `git status --short`.
3. Record branch and latest commit.
4. Identify the current workstream.
5. Inspect current owner files before change.
6. Follow Audit -> Build -> Install -> Validate -> Live test -> Clean -> BOOKSYNC -> Stage -> Commit -> Push.

### Current project position
- Latest published documentation milestone before this change: `339f04b`.
- Current validated workstream: Estate Configuration authority.
- Current uncommitted product scope: five Estate Configuration owner files.
- Required next gate: install this BOOKSYNC pack, validate the combined diff, then commit and push the product and documentation milestone.

### Estate Configuration completion record, 17 August 2026
- Completion status: accepted after static, runtime, authority, privacy, consistency and visual validation.
- API authority: `jom-admin-estate-configuration-authority-v3` at `/api/admin/estate-configuration`.
- Page: `/admin/estate-configuration`; selected-site continuation: `/site-workspace/<site-key>`.
- Current estate evidence: 4 monitored sites, 2 unique monitored products, 6 proven site-product assignments and 100% product coverage.
- Current administrative ownership: 4 of 4 sites, 33 role-assignment rows and 100% coverage. Role assignments are not unique people.
- Marketplace Apps: unavailable through the current JOM integration. Browser-session Jira gateway candidates existed, but Admin Bearer returned HTTP 406 and OAuth Bearer returned HTTP 401 across the four-site endpoint audit. No app records or fabricated counts are published.
- Runtime status: `ok_with_limitations`; Marketplace Apps is the single non-blocking limitation; blocking actions: 0.
- Privacy boundary: no personal ownership records, email addresses, account IDs, directory IDs, resource identifiers, cloud IDs, credentials, headers or raw Connected Apps payloads are returned by the page contract.
- Validation owners: `scripts/validate_estate_configuration_v1.py`, ``, ``, `scripts/validate_estate_resource_ari_correction_v1.py`, `scripts/validate_monitored_product_authority_v1.py`, `scripts/validate_marketplace_app_limitation_authority_v1.py`.
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

### 18 August 2026 - Estate Configuration validator hygiene

#### Decision

Two obsolete Estate Configuration validators were deleted as dead code rather than archived:
- `scripts/validate_estate_configuration_inventory_v3.py`
- `scripts/validate_estate_configuration_ui_refinement_v1.py`

#### Evidence and reason

The inventory v3 validator required Marketplace Apps presentation, `marketplace_app_count`, `estate_marketplace_app_authority_v1.json` and `ok_with_limitations` inside the active Estate Configuration presentation owner. The approved Marketplace authority audit subsequently proved that installed Marketplace App inventory could not be safely published, and the presentation was intentionally removed.

The earlier UI-refinement validator required `ec-products-note`, while the approved two-metric refinement explicitly removed that element. Both validators therefore contradicted the current accepted owner files and the passing Marketplace UI-removal validator. They no longer tested the approved implementation.

#### Current validation ownership

The current Estate Configuration validation set is:
- `scripts/validate_estate_configuration_v1.py`
- `scripts/validate_estate_configuration_marketplace_ui_removal_v1.py`
- `scripts/validate_estate_resource_ari_correction_v1.py`
- `scripts/validate_monitored_product_authority_v1.py`
- `scripts/validate_marketplace_app_limitation_authority_v1.py`
- `scripts/validate_estate_configuration_booksync_v3.py`
- `scripts/validate_estate_configuration_refinement_booksync_v1.py`

No archive copy is retained in the active repository. Git history remains the recovery authority for deleted code. The Foundation Recovery Audit remains the current workstream, with FR-001 Users & Access drill-down gates next.

<!-- JOM_PROJECT_INVENTORY_GOVERNANCE_PHASE2_BOOKSYNC_V1_START -->

## 19 August 2026 - Project Inventory and Governance Projects Phase 2

### Decision and delivered architecture

Project Inventory is now an authority-backed, read-only operational capability in JOM. The approved collector owner is `app/builders/project_inventory_authority_v1.py`, and the generated contract is `runtime/data/project_inventory_authority_v1.json`.

The automatic Admin refresh owner, `app/runtime/admin_enriched_chain.py`, now executes `app.builders.project_inventory_authority_v1` and validates the generated contract immediately after collection. The chain fails closed when any monitored site fails, pagination is incomplete, counts do not reconcile, site/project key pairs are incomplete, or duplicate site/project keys exist.

The dedicated read-only API is `/api/governance/projects`. The Governance Projects page is `/reports/governance/projects`, owned by:

- `templates/governance_projects.html`
- `static/js/jom_governance_projects_v1.js`
- `static/css/jom_governance_projects_v1.css`
- `scripts/validate_project_inventory_governance_integration_v1.py`

The existing Governance Report page and JavaScript remain untouched.

### Proven runtime evidence

The accepted Project Inventory contract passed all static, runtime, privacy, Flask-render, and shared-layout gates:

- Contract status: `ok`
- Monitored sites: 4
- Successful sites: 4
- Failed sites: 0
- Visible projects: 92
- Collected project rows: 92
- Duplicate site/project keys: 0
- Pagination complete for every monitored site: true
- Safe to publish Project Inventory: true
- Read-only API: true
- Forbidden response fields detected: 0

The API returned 92 records and exposed no cloud IDs, access tokens, refresh tokens, authorization headers, account IDs, email addresses, or unsupported identity data.

### User interface

The placeholder Governance Projects page was replaced with the live 92-project inventory. The page provides search and filters for site, project type, style, privacy, simplified state, and category. The page uses the established standalone JOM HTML shell, includes `_nav.html`, and applies the shared `jom-shell` layout contract so the fixed navigation does not overlap page content.

### Honest unavailable areas

The following remain explicitly unavailable because the current authority does not prove them:

- Project Leads
- Project Owners
- Archived Projects
- Inactive Projects
- Project Permissions
- Project Governance

Project owner semantics are not inferred from project lead. Archive state, inactivity, permissions, and governance will require separate authority collectors and validated contracts before they can be displayed as truth.

### Validation ownership

The active validators are:

- `scripts/validate_project_inventory_authority_v1.py`
- `scripts/validate_project_inventory_governance_integration_v1.py`

The integration validator verifies the collector-chain registration, fail-closed postconditions, API privacy boundary, page assets, standalone Jinja shell, Flask HTTP 200 rendering, shared navigation-offset shell, and live contract reconciliation.

### Clean implementation boundary at the commit gate

The intended implementation boundary is exactly:

- `app/runtime/admin_enriched_chain.py`
- `app/web.py`
- `app/builders/project_inventory_authority_v1.py`
- `templates/governance_projects.html`
- `static/js/jom_governance_projects_v1.js`
- `static/css/jom_governance_projects_v1.css`
- `scripts/validate_project_inventory_authority_v1.py`
- `scripts/validate_project_inventory_governance_integration_v1.py`
- `runtime/data/project_inventory_authority_v1.json`

Unrelated runtime drift was restored before BOOKSYNC. Extracted delivery folders were removed from the repository root. Nothing was staged before the BOOKSYNC gate.

### Working rules preserved

Continue using Luke's audit-first workflow:

1. Surface repository and live/runtime evidence before conclusions.
2. Do not present assumptions as truth.
3. Report unavailable data as unavailable.
4. Create missing authority only through a real collector, contract, and validation gates.
5. Use full owner-file replacements delivered as downloadable packs, not patches, snippets, or manual edits.
6. Use Windows PowerShell commands with actual repository paths and visible single-line commands.
7. Keep reports and temporary evidence out of the repository root.
8. Validate, BOOKSYNC, inspect the exact Git boundary, then stage and commit.

### Current and next workstream

Current workstream: Project Inventory and Governance Projects Phase 2 is implemented and validated, pending BOOKSYNC installation and final commit-gate validation.

Immediate next step: install this BOOKSYNC pack, validate the documentation boundary, stage only the approved implementation and BOOKSYNC owners, inspect the staged diff, then commit and push.

After the commit: continue Project Governance only by auditing for new supported authorities. Do not infer Project Leads, Project Owners, Archived Projects, Inactive Projects, Project Permissions, or Project Governance from existing Project Inventory fields.

<!-- JOM_PROJECT_INVENTORY_GOVERNANCE_PHASE2_BOOKSYNC_V1_END -->

### 3 September 2026 - Project Owner Live Authority Correction v1

#### Correction reason
The first Project Owner integration validator and BOOKSYNC record retained the earlier evidence-time totals of 92 projects, 69 governance-defined owners, 23 owner gaps, 75.0% coverage, and 20 distinct owners. A later automatic live refresh changed the current authority. The fixed-count validator correctly exposed that the documentation no longer matched runtime truth, but fixed historical totals are not valid long-term acceptance criteria for a live operational console.

#### Current live authority
The current Project Owner Authority contract was generated at `2026-09-03T08:18:37Z` and reports:
- Authority status: `partial`.
- Projects reconciled: 76.
- Projects with governance-defined owner: 73.
- Projects without a published governance-defined owner: 3.
- Owner coverage: 96.1%.
- Distinct governance-defined owners: 21.
- Owner source: `runtime/data/project_lead_authority_v1.json`.
- Owner type: `governance_defined_space_owner`.
- Native Jira owner field present: false.

These values supersede the earlier 92-project snapshot as current operational evidence. They remain time-sensitive and must not be hard-coded into future consumers or validators.

#### Dynamic validation rule
Project Owner validation now proves relationships rather than historical totals. The validator requires:
- Project Inventory, Project Lead, and Project Owner contracts to be present and publishable.
- Project Owner project count to equal the current Project Lead project count.
- Project Owner site/project key pairs to equal the current Project Lead key pairs.
- Every published owner to derive only from the matching Project Lead display name.
- Owner count, gap count, coverage percentage, and distinct-owner total to reconcile to current rows.
- Governance owner semantics to remain proven.
- Native Jira owner semantics and native owner-field presence to remain false.
- Account IDs, emails, and raw responses to remain absent.
- The loopback API to reconcile to the current runtime contract and remote access to remain denied.

The validator does not require the current counts to remain 76, 73, 3, 96.1%, and 21. Legitimate live changes are accepted only when all contracts and relationships reconcile.

#### Live dependency order
The required authority order remains:
1. Project Inventory refreshes from current Jira project authority.
2. Project Lead refreshes against the current Project Inventory and approved named identity authority.
3. Project Owner derives from the current Project Lead authority under the GLI rule that Project Lead is the owner of the project space.

An old report, retained project list, or historical count must never be used as current Project Owner truth.

#### Current boundary and next gate
Current workstream: install the Project Owner Live Authority Correction v1 pack, validate the dynamic authority chain and eight BOOKSYNC owners, run `git diff --check`, inspect the exact milestone boundary, then stage, commit, and push. After clean closeout, continue with Governance Projects UX Phase 1 using live authority contracts rather than fixed evidence-time counts.

## 8 September 2026 - Foundation Recovery closeout and current continuation

### Evidence-backed current state

This record updates the definitive JOM continuity position from the later runtime-alignment reports, retained validators, repository-cleanup validation and live checks completed on 8 September 2026. Earlier Foundation Recovery entries remain historical evidence, but their open-finding list is superseded by this current-state record where closure is proven.

- **FR-001 Users & Access drill-downs:** verified resolved. The current `runtime/data/users_access_actionable_drilldown_v1.json` contract regenerates with `status: ok`, `authority.safe_to_serve: true`, current freshness, complete organisation and directory pagination, supported categories available, email storage disabled, and export, download and write actions disabled. The Not invited population remains honestly unavailable because the tested Atlassian APIs do not expose that administration state.
- **FR-002 Unified runtime refresh status:** verified resolved. `runtime/data/runtime_refresh_status.json` exists and records canonical execution lifecycle and completion evidence.
- **FR-003 Refresh architecture:** verified resolved. Runtime Truth Alignment v1.1 Corrected, Runtime Finalization Alignment, Runtime Truth Chain validation, and Runtime Status / Source Health UX validation passed against the canonical architecture.
- **FR-004 Timestamp meaning consistency:** open and current. Consumers must distinguish live collection time, derived-contract time, refresh completion time, and configuration or authority-change time. File modification time or an unclassified `generated_at_utc` value is not sufficient proof of timestamp meaning.
- **FR-005 Placeholder and legacy surface classification:** open and next. Runtime Status and Source Health now have passing current-contract validation, but Discovery and remaining legacy or placeholder surfaces require explicit page-by-page classification and acceptance.

### Product Access authority evidence

The live Product Access collector `app/builders/estate_product_access.py` regenerated `runtime/data/estate_product_access.json` and `runtime/data/estate_access_truth.json` on 8 September 2026.

- Status: `partial`
- OAuth-accessible Jira resources: 6
- Successfully collectible application-role sites: 5
- Jira role rows: 5
- Live Jira product users across collectible resources: 169
- Reported seat limit: 12,150
- Reported remaining seats: 11,981
- Error sites: 1

`gli-usa` returned HTTP 403 with `Tenant is restricted: user-cancellation`. This is an Atlassian-controlled tenant restriction, not a JOM collector defect. The 169 total is current live authority for five collectible resources and is not presented as complete coverage of all six OAuth-accessible resources. No stale static Product Access fallback was used.

### Users & Access live evidence

The actionable drill-down builder was run directly on 8 September 2026 and reported 1,218 organisation accounts, 145 directory accounts, 92 MFA-disabled accounts, 4 organisation administrators, 4 site administrators, 41 user-access administrators, 1 high-access-concentration account, 7 unmanaged accounts, and zero suspended, deactivated or deletion-marked accounts. These are time-sensitive evidence values and must not be hard-coded into consumers or validators.

### Current and next workstream

- **Current phase:** Foundation Recovery closeout and runtime-truth hardening.
- **Current workstream:** FR-004 Timestamp Meaning Consistency audit.
- **Next workstream:** FR-005 Placeholder and Legacy Surface Classification audit.
- Do not reopen FR-001, FR-002 or FR-003 unless an owner changes, a retained validator fails, or new live evidence contradicts this record.
- Do not classify the `gli-usa` restriction as a JOM defect unless a later live Atlassian response proves a different tenant state.

### Working and Git rules

Continue: `Audit -> Build -> Install -> Validate -> Live test -> Clean -> BOOKSYNC -> Stage -> Commit -> Push`.

Use complete downloadable packs and full owner-file replacements only. Do not use patches, snippets, manual edits, wrappers or overlay layers. Surface repository and runtime evidence before conclusions, report unavailable authority as unavailable, keep temporary artefacts out of the repository root, run `git diff --check` before staging, inspect the exact milestone boundary, and run `git diff --cached --check` after staging.

### 8 September 2026 - Site Workspace and Discovery operational completion closeout

#### Accepted milestones

Two consumer-integration milestones were installed, validated, isolated from unrelated runtime drift, committed to `main`, and accepted:

- **Site Workspace Project Authority Integration**, commit `7a51d3ec489c4405de285fe136a65f4957f950ae` (`7a51d3e`), message `Site Workspace: integrate project authority`.
- **Discovery Authority Integration**, commit `ec38a54d576ffb68d621df83575593146dc17d82` (`ec38a54`), message `Discovery: integrate existing authority`.

#### Site Workspace current owner and authority position

Site Workspace now consumes the existing governance project authorities for the selected site. No new collector, runtime authority contract, or backend API was created.

Owner boundary:

- `templates/site_workspace.html`
- `static/js/jom_site_workspace_shell_v1.js`
- `static/css/jom_site_workspace_shell_v1.css`
- `scripts/validate_site_workspace_project_integration_v1.py`

Reused read-only routes:

- `/api/governance/projects`
- `/api/governance/projects/leads`
- `/api/governance/projects/owners`

The selected-site surface now presents project inventory, project lead authority, governance-defined space-owner authority, and governance coverage or gap state. Marketplace Apps and Automation remain explicitly unavailable where current authority does not prove those populations.

#### Discovery current owner and authority position

The Admin Discovery placeholder was replaced by a dedicated read-only consumer of the existing Discovery authority. No new collector, runtime authority contract, or backend API was created.

Owner boundary:

- `templates/admin_discovery.html`
- `static/js/jom_admin_discovery_v1.js`
- `static/css/jom_admin_discovery_v1.css`
- `scripts/validate_discovery_authority_integration_v1.py`

Reused read-only routes:

- `/api/estate/discovery-authority`
- `/api/estate/discovery-authority/coverage`

Discovery now presents current discovered identity scope, lifecycle review items, monitored classification, and source coverage. Lifecycle decisions remain owned by Estate and Site Review. Static fallback remains disabled. Retired-site population remains unavailable unless a current authority contract explicitly publishes it.

#### Foundation Recovery and surface-classification position

- FR-001, FR-002, and FR-003 remain verified resolved.
- FR-004 timestamp meaning consistency remains an evidence-controlled limitation until every affected consumer has been proven to distinguish collection, derivation, refresh completion, and authority-change time. This closeout does not fabricate closure of FR-004.
- FR-005 is materially reduced: Runtime Status and Source Health already had passing current-contract validation, Site Workspace project authority is now integrated, and Discovery is no longer a static placeholder. Any remaining surface must still be classified from its own owner and runtime evidence rather than by broad programme assumption.

#### Repository state at continuity gate

The product commits are complete. The working tree still contains unrelated generated runtime drift and untracked audit or report artefacts. These were deliberately excluded from both product commits and must not be deleted, staged, or committed without controlled classification. Known outstanding local items include:

- modified files under `runtime/data/`;
- `builders.txt`;
- `scripts.txt`;
- `scripts/validate_runtime_truth_chain_alignment_v1.py`;
- `test-validator-output.txt`.

The current authoritative next workstream is **Controlled Repository Hygiene Classification**. Classify each remaining item as `KEEP`, `COMMIT`, `GENERATED_RUNTIME`, `REPORT_ONLY`, `TRANSIENT`, or another explicitly justified category before taking action.

#### Continuation and Git gate

After installing this BOOKSYNC pack:

1. Run the packaged BOOKSYNC validator.
2. Run `git diff --check`.
3. Inspect `git status --short`.
4. Stage only the nine BOOKSYNC owners and the packaged BOOKSYNC validator.
5. Run `git diff --cached --check` and inspect the staged boundary.
6. Commit the continuity milestone separately from runtime drift.
7. Do not push or clean unrelated files unless the current operator workflow explicitly reaches that gate.

Continue using full owner-file replacements and complete downloadable packs. No patches, snippets, manual editing, wrappers, or overlay layers. Conclusions must remain backed by repository, validator, API, or live runtime evidence.
### 14 September 2026 - Command Centre UX Phase 4.3 closeout

#### Accepted outcome
- Baseline commit before this uncommitted milestone: 3b8b6b9, Command Centre UX Phase 3: monitoring wall and colour harmonisation.
- Current milestone: Command Centre UX Phase 4.3, Continuous Telemetry Recorder.
- Status: implemented, validated and visually accepted; pending BOOKSYNC installation, exact-boundary staging, commit and push.
- The Command Centre is now monitoring-first. A compact operational header is followed by the Monitoring Wall, monitored-estate and current-evidence areas, then the Action Required workflow.
- The fixed right operations rail is retained and contained within the viewport. Monitoring Coverage, Estate Snapshot and Operational Status remain in one rail with internal scrolling where required.
- Runtime, Source Health, Discovery and Users & Access use gapless continuous right-to-left recorder tracks. Each track contains two equal waveform segments in a 200 percent flex track translated exactly 50 percent, preventing blank gaps and visible restarts.
- Travelling dots, whole-wave vertical bobbing and SVG path morphing are absent. Reduced-motion handling is retained.
- The wall uses the established JOM blue, neutral and semantic healthy, review and critical palette.

#### Authority and operational boundary
- Page: /home.
- Existing read-only information route: /api/workspace/command-centre.
- No backend route, collector, runtime contract or authority source changed.
- Animation visualises the state loaded in the current Command Centre contract. Animation is not evidence of a network request, continuous poll or live collector execution.
- The current-evidence Contract served value is request-serving evidence. It must not be interpreted as collection time, derived-authority time or an authority-change timestamp. FR-004 Timestamp Meaning Consistency remains open.
- Command Centre is no longer a legacy-placeholder presentation for FR-005 purposes. This records accepted consumer presentation and operator workflow only; it does not fabricate closure of FR-004 or claim new collector authority.

#### Current owners
- templates/home.html
- static/js/jom_command_centre_completion_v1.js
- static/css/jom_command_centre_completion_v1.css
- scripts/validate_command_centre_ux_phase1_v1.py
- scripts/validate_command_centre_ux_phase4_3_v1.py

#### Validator hygiene
- Permanent validation owners for the accepted state are scripts/validate_command_centre_ux_phase1_v1.py and scripts/validate_command_centre_ux_phase4_3_v1.py.
- The following intermediate milestone and delivery validators are obsolete after Phase 4.3 acceptance and must be removed before staging: scripts/validate_command_centre_ux_phase4_v1.py, scripts/validate_command_centre_ux_phase4_jom_colour_owner_v1.py, scripts/validate_command_centre_ux_phase4_1_v1.py, scripts/validate_command_centre_ux_phase4_1_eof_v1.py, scripts/validate_command_centre_ux_phase4_2_v1.py and scripts/validate_command_centre_ux_phase4_3_eof_v1.py.
- Git history and the delivery packs remain the recovery evidence for those intermediate gates. They are not active repository authority.

#### Validation and acceptance evidence
- Phase 1 regression validation passed.
- Phase 4.3 continuous-recorder validation passed after the CSS terminal-newline correction.
- /home returned HTTP 200.
- /api/workspace/command-centre returned HTTP 200.
- Fixed right-rail bindings and viewport containment passed.
- JOM colour ownership, monitored-site filtering, no-polling boundary and reduced-motion handling passed.
- Luke visually accepted the final continuous recorder on 14 September 2026.
- Generated runtime drift was preserved outside the repository and restored before BOOKSYNC.

#### Commit boundary and continuation
- Product owners to stage: templates/home.html, static/js/jom_command_centre_completion_v1.js and static/css/jom_command_centre_completion_v1.css.
- Retained validators to stage: scripts/validate_command_centre_ux_phase1_v1.py and scripts/validate_command_centre_ux_phase4_3_v1.py.
- BOOKSYNC owners to stage: BOOKSYNC Guide.md, GitHub Repository Record.json, JOM Change History.md, JOM Guide v2 Additions.md, JOM Progress and Improvements.md, JOM Quick Start.md, JOM Recovery Guide.md, JOM System and File Map.md and The Jira Observation Monitor Guide.md.
- BOOKSYNC validator to stage: scripts/validate_command_centre_ux_phase4_3_booksync_v1.py.
- Immediate next step: install this BOOKSYNC pack, run the product and BOOKSYNC validators, delete the six obsolete untracked validators through the packaged runner, inspect git status and git diff, stage only the approved fifteen-file boundary, run git diff --cached --check, inspect staged names, commit and push.
- Next workstream after clean push: continue FR-005 Placeholder and Legacy Surface Classification with the next unaccepted surface selected from current repository evidence. FR-004 remains open.
- Working rule remains Audit -> Build -> Install -> Validate -> Live test -> Clean -> BOOKSYNC -> Stage -> Commit -> Push, using full owner-file replacement packs and no manual editing.

### 16 September 2026 - Controlled Repository Hygiene: proven duplicate-owner removal

- Commit `3b37d87` removed duplicate runtime owners `app/runtime/backup_runtime_chain.py` and `app/runtime/runtime_backup_chain.py`, retaining `app/runtime/snapshot_controller.py`.
- The same commit removed duplicate validator `scripts/validate_project_owner_authority_integration_v1.py`, retaining `scripts/validate_project_owner_live_authority_v1.py`.
- SHA256 equality and repository-consumer review supplied the deletion evidence. Git history remains recovery authority.
- Recovery tag: `repo-hygiene-before-booksync-alignment`.


### 16 September 2026 - Repository Classification Model closeout

#### Corrected audit rule
Repository ownership cannot be inferred from folder names, age, or missing filename references. Classification requires filesystem evidence, content hashes, active consumers, validators, runtime behaviour and BOOKSYNC authority. A missing reference alone is not deletion authority.

#### Classification model
- **AUTHORITY_CONTRACT:** Published authority inputs consumed by builders, routes, validators or downstream authority chains.
- **LIFECYCLE_AUTHORITY:** Operator decisions, onboarding state, monitoring approvals, access validation and lifecycle history.
- **OPERATIONAL_STATE:** Execution lifecycle, refresh telemetry, current runtime status and process state.
- **AUDIT_EVIDENCE:** Freshness, reliability or source-authority assessment outputs that are not primary business authority.
- **REPORT_ONLY:** Generated reports and local audit material that are not tracked repository authority.
- **TRANSIENT:** Disposable caches, compiled files and temporary runtime or snapshot folders.
- **HISTORICAL_RECOVERY:** Unique historical checkpoints retained because their content differs from current owners.
- **OPERATIONAL_RECOVERY:** Current rollback and runtime-recovery material.

#### Proven authority contracts in runtime/data
`site_registry.json`, `admin_truth_v2.json`, `estate_access_truth.json`, `estate_product_access.json`, `user_footprint.json`, `named_site_access_authority_v1.json`, `named_user_display_identity_v1.json`, `verified_active_jira_users_v1.json`, `users_access_actionable_drilldown_v1.json`, `project_governance_named_identity_authority_v1.json`, `project_inventory_authority_v1.json`, `project_lead_authority_v1.json`, `project_owner_authority_v1.json`, `estate_admin_contacts_v1.json`, `estate_monitored_product_authority_v1.json`, `estate_site_resource_mapping_v1.json`, and `organisation_discovery.json`.

These files regenerate in operation but also act as current authority contracts. They must not be treated as disposable solely because they reside under `runtime/data`.

#### Proven lifecycle authority
- `runtime/data/site_access_validation.json`
- `runtime/data/site_lifecycle_decisions.json`
- `runtime/data/site_onboarding_review.json`

#### Proven operational state
- `runtime/data/runtime_execution_status.json`
- `runtime/data/runtime_execution_history.json`
- `runtime/data/runtime_refresh_status.json`
- `runtime/data/product_access_refresh_status.json`
- `runtime/data/estate_resource_authority_refresh_status_v1.json`

#### Proven audit evidence
- `runtime/data/source_freshness_audit.json`
- `runtime/data/source_reliability_status.json`
- `runtime/data/organisation_auth_source_audit.json`

#### Reports, transient material and recovery
- `reports/*`: REPORT_ONLY. The audit counted 87 local report inventory lines and found no tracked files under `reports`.
- `__pycache__/`, `*.pyc`, `runtime_data/` and `snapshots/`: TRANSIENT.
- `backups/foundation_recovery_booksync_v1/` and `backups/estate_marketplace_ui_removal_v1/`: HISTORICAL_RECOVERY because compared content differed from current owners.
- `backups/latest_runtime/`: OPERATIONAL_RECOVERY.

#### Validator-estate result
The Command Centre, Discovery, Governance Users, Governance Projects, Runtime UX, Runtime Truth, Source Health, Project Lead, Project Owner, Estate Configuration, Marketplace and Connected Apps validator families were reviewed. Cumulative validators proving different accepted layers remain retained.

Commit `d6e5a5c` (`repo hygiene: retire obsolete command centre validators`) removed:
- `scripts/validate_command_centre_ux_phase3_jom_colour_v1.py`
- `scripts/validate_command_centre_ux_phase3_render_correction_v1.py`
- `scripts/validate_command_centre_ux_phase3_v1.py`
- `scripts/validate_command_centre_ux_phase4_3_booksync_eof_v1.py`

Retained Command Centre validators remain:
- `scripts/validate_command_centre_ux_phase1_v1.py`
- `scripts/validate_command_centre_ux_phase4_3_v1.py`
- `scripts/validate_command_centre_ux_phase4_3_booksync_v1.py`

#### Hygiene commits and continuation
- `3b37d87`: `repo hygiene: remove proven duplicate owners`.
- `1c1c457`: `BOOKSYNC: repository hygiene duplicate owner cleanup`.
- `d6e5a5c`: `repo hygiene: retire obsolete command centre validators`.

The classification model is established. Further deletion requires positive duplication or obsolescence evidence plus authority, consumer, BOOKSYNC and exact-boundary review. Install this nine-owner replacement pack, run `git diff --check`, stage only the nine BOOKSYNC owners, run `git diff --cached --check`, commit the classification closeout, then reassess whether further hygiene work is justified before resuming Docker, deployment, FR-004, FR-005 or feature development.

#### 21 September 2026 - Commerce authority discovery and authentication boundary

##### Proven discovery evidence

An authenticated Atlassian billing-administrator browser session returned the selected transaction-account Commerce hierarchy. The response included effective permissions, one invoice group, payment-method type, invoices, seven active entitlements, products and Marketplace apps, subscription status, billing cycle, licensed quantity, pricing-plan references and tier structure, start and end timestamps, orders and billing administrators. Pagination reported `hasNextPage = false`. The selected account reported USD and DEFERRED payment method type.

The GraphQL response returned useful data together with field-level errors for `displayInfo`, `billEstimateForMeteredChargeElements` and `billEstimateWithPermissionCheck`. This evidence is classified as `partial_success`. Failed resolver fields remain unavailable and must not be inferred from surrounding commercial records.

##### Authentication authority audit

The existing JOM service-account OAuth client successfully completed token exchange with HTTP 200 and received a one-hour Bearer token. A read-only request reached `https://api.atlassian.com/graphql` with HTTP 200, but the public OAuth schema rejected `commerceExp_queryIfAuthenticated2` as undefined. This proves service-account authentication and GraphQL gateway reachability, but does not prove Commerce schema availability or billing-account inventory through that route.

The Atlassian service-account API-token scope catalogue exposed 519 selectable scopes. Searches found no Commerce or billing scopes. Subscription results were Guard-specific, and entitlement results were Jira Service Management customer-entitlement scopes rather than Atlassian Commerce billing entitlement authority. No scoped API token was created.

##### Architectural decision and safety boundary

- Commerce GraphQL data source: proven through a billing-admin browser session.
- Billing-admin field authorisation: proven for the supplied transaction account.
- Commercial data completeness: partial success.
- Existing JOM OAuth service account: authenticated, but Commerce schema unavailable through the tested public OAuth GraphQL route.
- Scoped service-account API token: no relevant Commerce or billing scope offered; not created.
- Personal browser session: discovery evidence only; not an accepted production collector source.
- Dedicated organisation-owned JOM Commerce Collector account with organisation-admin and billing-admin roles: candidate architecture only.
- Supported unattended credential for that candidate account: unproven.
- Production Commerce collector: blocked only on supported unattended authentication authority.

Do not place browser cookies, session identifiers, copied request headers, personal credentials or private Commerce response bodies in `.env`, the repository, a container image or BOOKSYNC. Do not infer unavailable bill estimates or display information. Do not modify the Licensing & Billing product implementation until supported unattended authentication is proven and a collector, runtime contract, privacy boundary and validator set exist.

##### Current workstream and next step

Current workstream: Commerce GraphQL Authentication Authority Audit closeout. The evidence is discovery and audit authority, not an implemented production collector and not a completed Licensing & Billing milestone.

Immediate next step: install and validate this nine-owner BOOKSYNC replacement pack, inspect the exact documentation-only Git boundary, then stage, commit and push only the approved BOOKSYNC owners. After clean closeout, seek explicit Atlassian-supported authentication authority for an organisation-owned billing-admin collector identity before provisioning a privileged account or changing JOM code.

## 23 September 2026 - Controlled recovery and page-by-page authority alignment milestone

### Current milestone position
- Branch at BOOKSYNC gate: ``.
- Baseline HEAD before this milestone is committed: `ce742c4a3472a13f42750b54a5a6e9b0b3bb3645`.
- The recovery sequence retained audit-first, read-only authority boundaries and Luke-controlled page progression.
- Accepted/parked surfaces in this milestone: Source Health, Runtime, Governance Overview/Projects/Users, Governance unavailable capability boundaries, Estate Report, Executive Report, Admin Overview, and Admin Estate Configuration.
- Governance Configuration, Permissions and Policy Compliance remain unavailable/not proven where no approved authority contract exists.
- Commercial billing remains unavailable until a proven commercial authority exists.

### Authority and presentation corrections
- Runtime separates execution health from authority quality. Present status-neutral contracts are not treated as unavailable; schema-owned states such as Partial and Attention remain visible.
- Source Health remains the detailed owner for current source-authority findings; Estate Report and Executive Report surface those findings without recreating specialist diagnosis.
- Governance preserves Project Lead and Project Owner `partial` authority while continuing to serve valid records. Browser-owned fallback metrics and the overlapping Governance Users review total were removed from accepted consumers.
- Estate Report and Executive Report consume the approved Verified Active Jira Users authority and keep product assignments distinct from verified-active users.
- Executive Report no longer treats an unowned 100 percent monitoring threshold as policy.
- Admin Overview now consumes the existing Discovery authority rather than hard-coding Discovery as unavailable.
- Admin Estate Configuration remains scoped to monitored-product and administrative-ownership configuration gates; its 33 ownership rows are described as administrative ownership assignments, not unique people.

### Runtime retention and repository hygiene
- Controlled cleanup retained exactly five modified milestone runtime contracts: `runtime/data/runtime_refresh_status.json`, `runtime/data/site_registry.json`, `runtime/data/source_freshness_audit.json`, `runtime/data/source_reliability_status.json`, and `runtime/data/product_access_refresh_status.json`.
- Other modified runtime snapshots and access-audit log drift were restored to HEAD after explicit classification.
- `reports/*` remains report-only evidence and is not part of the tracked milestone.
- Untracked `INSTALL_AND_VALIDATE.ps1` and the `JOM Living Guide Architecture & Portfolio/` directory remain outside this milestone and were not cleaned, staged or promoted by this BOOKSYNC.

### Current owner and architecture direction
- `app/web.py` remains the primary route/presentation-contract owner.
- Specialist pages remain evidence owners; overview/reporting surfaces are thin consumers and must not duplicate authority or policy calculations in the browser.
- Command Centre must eventually surface genuine Source Health and Runtime warnings/errors with reasons and investigation routes while Source Health/Runtime retain detailed evidence ownership.
- The platform remains a read-only operational console. Unsupported values remain unavailable rather than inferred or hard-coded.

### Current next step
- Validate this BOOKSYNC boundary together with the current product/runtime diff.
- Stage only the approved product owners, the five retained runtime contracts, and the nine definitive BOOKSYNC owners after exact-boundary inspection.
- Run `git diff --cached --check` and inspect staged names before commit/push.
- After a clean milestone closeout, resume Admin page 3 of 7, Discovery, under Luke-controlled page-by-page review.
- Do not proceed independently to later Admin pages.

