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
- Validation owners: `scripts/validate_estate_configuration_v1.py`, `scripts/validate_estate_configuration_inventory_v3.py`, `scripts/validate_estate_configuration_ui_refinement_v1.py`, `scripts/validate_estate_resource_ari_correction_v1.py`, `scripts/validate_monitored_product_authority_v1.py`, `scripts/validate_marketplace_app_limitation_authority_v1.py`.
- Commit gate: install these BOOKSYNC owners, validate product and documentation together, inspect staged scope, then commit and push.
- Next workstream: choose the next incomplete Admin page only after this milestone is clean and pushed. Discovery remains parked unless explicitly selected.
