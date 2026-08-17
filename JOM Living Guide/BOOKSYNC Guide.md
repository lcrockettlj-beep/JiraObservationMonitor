# BOOKSYNC Guide

Trigger word: `BOOKSYNC`.

When BOOKSYNC is invoked, update the current-state summary, affected page chapter, owner map, authority catalogue, progress register, change history, known limitations, current next step and rule changes. Validate paths against the repository. Documentation changes are staged with the product milestone. `GIT SAVE` includes BOOKSYNC before staging and commit. Minor command reruns or cleanup-only actions do not require a book update.

## Estate Configuration BOOKSYNC record
- Milestone authority: `jom-admin-estate-configuration-authority-v1`.
- Product owners: `app/web.py`, Estate Configuration template, dedicated JavaScript, dedicated CSS and validator.
- Validated authority: 4 sites, 100% tenant identity, 75% resource mapping, 75% ownership and 97 assignments.
- Known gaps: business classification, criticality, region, business unit, tags, partial resource mapping and partial ownership.
- Privacy boundary: no personal contact fields returned.
- Commit gate: stage product and documentation owners together only after diff validation.

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
