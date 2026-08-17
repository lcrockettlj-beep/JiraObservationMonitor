# The Jira Observation Monitor Guide

## How JOM Works, How It Is Built, and How Work Continues

**As-built baseline:** `main` at `29d1166b10da980da847f3ae8978e1191b24b8b9`
**Evidence date:** 14 August 2026
**Document status:** Living controlled guide

# 1. Executive Summary

Jira Observation Monitor (JOM) is a read-only operational console for observing an Atlassian estate through authenticated and runtime-backed authority. This guide records the system as built at branch `main` and commit `29d1166b10da980da847f3ae8978e1191b24b8b9` on 14 August 2026. The repository evidence identifies 184 tracked paths, 67 Python files, 34 HTML templates, 14 JavaScript files and 14 CSS files.

The defining engineering principle is truth before appearance. JOM must not invent a value merely to complete a dashboard. When evidence is absent, the correct output is unavailable. The guide is both a product explanation for non-technical readers and an owner reference for technical maintenance.

# 2. Purpose, Scope and Audience

This book combines a System Architecture Document, Technical Specification, As-Built Record, Build Book, Operations Runbook, Recovery Guide and continuity handbook. It supports operators, managers, auditors, maintainers and future Copilot conversations. It does not expose secrets, tokens, personal identifiers or credential values.

The book explains current ownership and known evidence. A filename being present does not, by itself, prove that the file is active website truth. Live behaviour and runtime authority remain the acceptance standard.

# 3. Operating Principles and Working Rules

- No assumptions as truth. If runtime or authenticated authority cannot prove a value, report it as unavailable.
- Do not present placeholders, estimates, screenshots, demonstrations, or stale snapshots as facts.
- User-facing truth must follow the live chain: page, browser code, API route, runtime contract, collector or builder, authenticated Atlassian authority.
- Audit the active owner, route, source and current file before making changes.
- Use single-owner implementation. No patch stacking, wrappers, sidecars, duplicate active pages or hidden overlays.
- Use exact user-provided paths and filenames.
- Deliver complete downloadable packs with extract, install, validate, clean, stage, commit and push workflow.
- Remove temporary packs and transient runtime logs before commit.
- BOOKSYNC is the documentation update gate before every Git save milestone.

# 4. Plain-Language Architecture

A user opens a page in a browser. The page template provides the visible structure. A JavaScript owner requests information from an application route. The route, mostly owned by `app/web.py`, reads or builds approved runtime contracts. Builders and collectors obtain or reconcile information from authenticated Atlassian sources. The route returns a privacy-safe response to the browser.

The normal evidence chain is:

Atlassian authority -> collector or builder -> runtime contract -> Flask route -> JavaScript binding -> page display.

If any link is absent, JOM must state that the information is unavailable or omit the unsupported element.

# 5. As-Built Repository Structure

`app/` contains the active application, route owner, builders, access reconciliation, registry logic, reporting and runtime operations. `templates/` contains visible page structures. `static/js/` contains browser behaviour and API bindings. `static/css/` contains page presentation. `runtime/data/` contains generated evidence contracts and operational state. `config/` contains controlled configuration inputs. `scripts/` contains operational entry points and health or cleanup utilities. `reports/` contains generated evidence and review documents. `backups/` is historical recovery material and is not automatically current website authority.

# 6. Main Application Owner

`app/web.py` is the primary web application owner. At the audited baseline it is approximately 256 KB and contains page routes, API routes, runtime readers, authority contract builders, lifecycle operations, monitoring refresh behaviour, OAuth callback handling, report generation and compatibility routes. Because this file owns many independent areas, every change must begin with a focused ownership and route audit. Full owner-file replacement is preferred over layered route overrides.

# 7. Authority and Runtime Information Model

Runtime contracts are durable machine-readable records used between collection, reconciliation and presentation. A valid JSON file is not automatically safe to display. Each consumer must respect the contract's status, freshness, scope, capability boundaries and privacy fields. Generated runtime files may change during live testing. Only deliberate milestone authorities should be committed; transient refresh drift and access logs should normally be restored or removed before commit.

# 8. Users and Access Case Study

Users & Access demonstrates the mature JOM pattern. The page combines organisation account authority, management coverage, MFA state, administrative assignments, user footprint, named site access, verified-active Jira evidence, privacy-approved display identity and actionable drill-downs.

The implementation preserves separation between product assignments and active users. Named-person views expose approved display names and access context while suppressing email and account identifiers. The Phase 1 endpoints are local-operator only, block remote access and export, and record privacy-safe access audit events. Not-invited users remain unavailable because the tested authority does not prove that population.

# 9. Security, Privacy and Read-Only Boundaries

JOM is designed as an observation console rather than a remote administration tool. Direct Atlassian links navigate an authorised operator to the official administration area; JOM does not perform the downstream write. Privacy controls minimise identity data, avoid exposing email or account identifiers in drill-down responses, disable export and download where not approved, and restrict Phase 1 identity views to loopback access. Credential files `.env`, `tokens.json` and `.auth_state.json` are excluded from the documentation evidence.

# 10. Build and Change Method

The standard delivery sequence is Audit -> Build -> Install -> Validate -> Live test -> Clean -> BOOKSYNC -> Stage -> Commit -> Push.

Audit proves the current owners, routes and runtime sources. Build produces full owner replacements. Install uses the exact repository root and exact filenames. Validation includes syntax, contract and security checks. Live testing confirms browser behaviour. Cleanup removes packs, caches, logs and unrelated runtime drift. BOOKSYNC updates this guide and continuity records. Staging contains only the intended product and documentation scope.

# 11. Operations Runbook

Start from the repository root. Check `git status --short` before changing anything. Run the application using the repository's established local method. Use page-specific refresh controls or approved builders rather than editing runtime JSON manually. Treat refresh outputs as operational drift until reviewed. When a page reports unavailable, trace the page, JavaScript fetch, API route, runtime file, builder and authenticated source in that order.

Daily checks should cover application health, runtime execution status, source freshness, source reliability, site registry alignment, product access refresh status and relevant page contracts.

# 12. Recovery and Continuity

After an interrupted session, first inspect branch, HEAD and working tree. Do not reapply packs blindly. Identify modified tracked files, untracked pack folders, transient logs and runtime drift. Restore unrelated runtime files only after confirming they are not the intended milestone. Re-run syntax and contract checks. Use the latest committed guide and Git history to locate the last complete milestone.

For a new conversation, provide the Quick Start section, current `git status --short`, latest commit, current workstream and relevant owner files. Broad repository re-audits should be avoided when the guide is current.

# 13. BOOKSYNC Continuity Rule

Trigger word: `BOOKSYNC`.

When BOOKSYNC is invoked, update the current-state summary, affected page chapter, owner map, authority catalogue, progress register, change history, known limitations, current next step and rule changes. Validate paths against the repository. Documentation changes are staged with the product milestone. `GIT SAVE` includes BOOKSYNC before staging and commit. Minor command reruns or cleanup-only actions do not require a book update.

# 14. Current State and Known Limitations

The audited baseline contains active authority page routes for Monitoring, Users & Access, Licensing & Billing, System Configuration, Executive Report, Estate Report and Governance Report. Users & Access has the deepest recently validated drill-down capability. Commercial billing remains unavailable without proven billing authority. Not-invited account population remains unavailable. Historical backup and snapshot material remains in the repository but is not accepted as current website truth. Automatic filename matching is only a candidate and requires human review where page names differ.

# 15. Evidence and Assurance Statement

This edition is based on uploaded repository inventories, Git evidence and the earlier Foundation Audit. It documents paths and relationships supported by that evidence. It does not claim that every route has been live-tested during book generation. Live acceptance remains page-specific. Counts and runtime statuses are time-sensitive and should always be read together with their evidence date.

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

# Appendix B. Runtime Information Catalogue

- `runtime\data\admin_directory_users.json`
- `runtime\data\admin_enriched_refresh_status.json`
- `runtime\data\admin_group_expansion.json`
- `runtime\data\admin_group_expansion_status.json`
- `runtime\data\admin_truth_v2.json`
- `runtime\data\backend_final_truth_chain_status.json`
- `runtime\data\estate_access_truth.json`
- `runtime\data\estate_admin_contacts_v1.json`
- `runtime\data\estate_admin_site_inventory_v1.json`
- `runtime\data\estate_discovery_authority_v1.json`
- `runtime\data\estate_product_access.json`
- `runtime\data\estate_site_resource_identity_catalog_...`
- `runtime\data\estate_site_resource_mapping_v1.json`
- `runtime\data\estate_site_tenant_identity_v1.json`
- `runtime\data\named_site_access_authority_v1.json`
- `runtime\data\named_user_display_identity_v1.json`
- `runtime\data\organisation_auth_source_audit.json`
- `runtime\data\organisation_discovery.json`
- `runtime\data\product_access_refresh_status.json`
- `runtime\data\runtime_execution_history.json`
- `runtime\data\runtime_execution_status.json`
- `runtime\data\site_access_validation.json`
- `runtime\data\site_lifecycle_decisions.json`
- `runtime\data\site_onboarding_review.json`
- `runtime\data\site_registry.json`
- `runtime\data\source_freshness_audit.json`
- `runtime\data\source_reliability_status.json`
- `runtime\data\users_access_actionable_drilldown_v1.json`
- `runtime\data\user_footprint.json`
- `runtime\data\verified_active_jira_users_v1.json`

# Appendix C. Python Component Catalogue

- `__init__.py`
- `app\web.py`
- `app\__init__.py`
- `app\access\admin_named_access_endpoint_probe.py`
- `app\access\collect_admin_group_expansion.py`
- `app\access\group_expansion_recovery_runner.py`
- `app\access\named_access_reconciliation.py`
- `app\access\named_access_recovery_plan.py`
- `app\access\named_access_recovery_runner.py`
- `app\access\named_access_truth_v2.py`
- `app\access\reconcile_named_access_truth_v2.py`
- `app\access\user_footprint_source.py`
- `app\access\user_footprint_unlock_runner.py`
- `app\access\__init__.py`
- `app\audits\audit_source_freshness.py`
- `app\audits\organisation_auth_source_audit.py`
- `app\audits\source_freshness.py`
- `app\audits\source_reliability.py`
- `app\audits\source_reliability_advisory.py`
- `app\audits\source_reliability_audit.py`
- `app\audits\__init__.py`
- `app\builders\admin_enriched_sources.py`
- `app\builders\admin_insight_engine.py`
- `app\builders\admin_truth_layer_v2.py`
- `app\builders\bind_operational_console_dark_ui.py`
- `app\builders\bind_operational_console_enhancements.py`
- `app\builders\bind_site_onboarding_review_ui.py`
- `app\builders\estate_admin_contacts.py`
- `app\builders\estate_product_access.py`
- `app\builders\named_site_access_authority_v1.py`
- `app\builders\named_user_display_identity_v1.py`
- `app\builders\organisation_discovery.py`
- `app\builders\product_access_sources.py`
- `app\builders\site_workspace_product_users_builder.py`
- `app\builders\users_access_actionable_drilldown_v1.py`
- `app\builders\verified_active_jira_users_v1.py`
- `app\builders\__init__.py`
- `app\collectors\__init__.py`
- `app\operational\operator_surface.py`
- `app\operational\__init__.py`
- `app\registry\apply_site_onboarding_control_layer_v1.py`
- `app\registry\run_site_onboarding_control_decision_v...`
- `app\registry\site_onboarding_control.py`
- `app\registry\site_registry_builder.py`
- `app\registry\site_registry_runtime.py`
- `app\registry\__init__.py`
- `app\reporting\export_reporting.py`
- `app\reporting\__init__.py`
- `app\runtime\admin_enriched_chain.py`
- `app\runtime\backup_runtime_chain.py`
- `app\runtime\operational_source_recovery.py`
- `app\runtime\runtime_backup_chain.py`
- `app\runtime\runtime_data_paths.py`
- `app\runtime\runtime_sources_refresh.py`
- `app\runtime\run_runtime_refresh_reliability_alignme...`
- `app\runtime\run_source_reliability_advisory_persist...`
- `app\runtime\snapshot_controller.py`
- `app\runtime\__init__.py`
- `app\shared\_project_bootstrap.py`
- `app\shared\__init__.py`
- `config\feature_flags.py`
- `config\__init__.py`
- `scripts\audit_organisation_auth_sources.py`
- `scripts\audit_source_freshness.py`
- `scripts\backend_runtime_freshness_snapshot_eliminat...`
- `scripts\build_site_registry.py`
- `_audit_jom_guide_foundation_v1\run_audit.py`

# Appendix D. Tracked Repository Catalogue

- `.gitignore`
- `__init__.py`
- `app/README.md`
- `app/__init__.py`
- `app/access/__init__.py`
- `app/access/admin_named_access_endpoint_probe.py`
- `app/access/collect_admin_group_expansion.py`
- `app/access/group_expansion_recovery_runner.py`
- `app/access/named_access_reconciliation.py`
- `app/access/named_access_recovery_plan.py`
- `app/access/named_access_recovery_runner.py`
- `app/access/named_access_truth_v2.py`
- `app/access/reconcile_named_access_truth_v2.py`
- `app/access/user_footprint_source.py`
- `app/access/user_footprint_unlock_runner.py`
- `app/audits/__init__.py`
- `app/audits/audit_source_freshness.py`
- `app/audits/organisation_auth_source_audit.py`
- `app/audits/source_freshness.py`
- `app/audits/source_reliability.py`
- `app/audits/source_reliability_advisory.py`
- `app/audits/source_reliability_audit.py`
- `app/builders/__init__.py`
- `app/builders/admin_enriched_sources.py`
- `app/builders/admin_insight_engine.py`
- `app/builders/admin_truth_layer_v2.py`
- `app/builders/bind_operational_console_dark_ui.py`
- `app/builders/bind_operational_console_enhancements.py`
- `app/builders/bind_site_onboarding_review_ui.py`
- `app/builders/estate_admin_contacts.py`
- `app/builders/estate_product_access.py`
- `app/builders/named_site_access_authority_v1.py`
- `app/builders/named_user_display_identity_v1.py`
- `app/builders/organisation_discovery.py`
- `app/builders/product_access_sources.py`
- `app/builders/site_workspace_product_users_builder.py`
- `app/builders/users_access_actionable_drilldown_v1.py`
- `app/builders/verified_active_jira_users_v1.py`
- `app/collectors/__init__.py`
- `app/operational/__init__.py`
- `app/operational/operator_surface.py`
- `app/registry/__init__.py`
- `app/registry/apply_site_onboarding_control_layer_v1.py`
- `app/registry/run_site_onboarding_control_decision_v1.py`
- `app/registry/site_onboarding_control.py`
- `app/registry/site_registry_builder.py`
- `app/registry/site_registry_runtime.py`
- `app/reporting/__init__.py`
- `app/reporting/export_reporting.py`
- `app/runtime/__init__.py`
- `app/runtime/admin_enriched_chain.py`
- `app/runtime/backup_runtime_chain.py`
- `app/runtime/operational_source_recovery.py`
- `app/runtime/run_runtime_refresh_reliability_alignment_v1.py`
- `app/runtime/run_source_reliability_advisory_persistence_v1.py`
- `app/runtime/runtime_backup_chain.py`
- `app/runtime/runtime_data_paths.py`
- `app/runtime/runtime_sources_refresh.py`
- `app/runtime/snapshot_controller.py`
- `app/shared/__init__.py`
- `app/shared/_project_bootstrap.py`
- `app/web.py`
- `backups/latest_runtime/current/latest_run_admin_enriched.json`
- `backups/latest_runtime/current/latest_run_admin_enriched_pretty.json`
- `backups/latest_runtime/current/latest_run_alerted.json`
- `backups/latest_runtime/current/latest_run_intelligence.json`
- `backups/latest_runtime/current/latest_run_safe_partial.json`
- `backups/latest_runtime/current/latest_snapshot.json`
- `backups/latest_runtime/current/snapshot_index.json`
- `backups/latest_runtime/latest_manifest.json`
- `config/__init__.py`
- `config/feature_flags.py`
- `config/monitored_sites.json`
- `config/site_onboarding_decisions.json`
- `continuous_improvement_register.md`
- `requirements.txt`
- `runtime/data/admin_enriched_refresh_status.json`
- `runtime/data/admin_truth_v2.json`
- `runtime/data/backend_final_truth_chain_status.json`
- `runtime/data/estate_access_truth.json`
- `runtime/data/estate_admin_contacts_v1.json`
- `runtime/data/estate_admin_site_inventory_v1.json`
- `runtime/data/estate_discovery_authority_v1.json`
- `runtime/data/estate_product_access.json`
- `runtime/data/estate_site_resource_identity_catalog_v1.json`
- `runtime/data/estate_site_resource_mapping_v1.json`
- `runtime/data/estate_site_tenant_identity_v1.json`
- `runtime/data/named_site_access_authority_v1.json`
- `runtime/data/named_user_display_identity_v1.json`
- `runtime/data/organisation_auth_source_audit.json`
- `runtime/data/organisation_discovery.json`
- `runtime/data/product_access_refresh_status.json`
- `runtime/data/runtime_execution_history.json`
- `runtime/data/runtime_execution_status.json`
- `runtime/data/site_access_validation.json`
- `runtime/data/site_lifecycle_decisions.json`
- `runtime/data/site_onboarding_review.json`
- `runtime/data/site_registry.json`
- `runtime/data/source_freshness_audit.json`
- `runtime/data/source_reliability_status.json`
- `runtime/data/user_footprint.json`
- `runtime/data/users_access_actionable_drilldown_v1.json`
- `runtime/data/verified_active_jira_users_v1.json`
- `scripts/audit_organisation_auth_sources.py`
- `scripts/audit_source_freshness.py`
- `scripts/audit_sprint10_phase1.ps1`
- `scripts/audit_sprint10_phase2.ps1`
- `scripts/backend_runtime_freshness_snapshot_elimination_v1.py`
- `scripts/build_site_registry.py`
- `scripts/health_check.ps1`
- `scripts/jom_health_check.ps1`
- `scripts/ops/preview_static_cleanup.ps1`
- `scripts/ops/run_alert_rules_once.ps1`
- `scripts/ops/run_auth_verification.ps1`
- `scripts/ops/run_intelligence_rules_once.ps1`
- `scripts/ops/safe_cleanup_apply.ps1`
- `scripts/ops/safe_cleanup_preview.ps1`
- `scripts/ops/setup_project.ps1`
- `scripts/restore_runtime_from_backup.ps1`
- `scripts/test_multi_user_poc.ps1`
- `static/css/jom_admin_licensing_billing_v1.css`
- `static/css/jom_admin_monitoring_v1.css`
- `static/css/jom_admin_system_configuration_v1.css`
- `static/css/jom_admin_users_access_v1.css`
- `static/css/jom_atlassian_command.css`
- `static/css/jom_command_centre_completion_v1.css`
- `static/css/jom_estate_lifecycle_v1.css`
- `static/css/jom_estate_report_v1.css`
- `static/css/jom_executive_report_v1.css`
- `static/css/jom_governance_report_v1.css`
- `static/css/jom_site_review_v1.css`
- `static/css/jom_site_workspace_shell_v1.css`
- `static/css/jom_site_workspace_v1.css`
- `static/css/jom_visual_consistency_v2.css`
- `static/fonts/texgyreadventor-regular.woff`
- `static/img/gli.svg`
- `static/js/jom_admin_licensing_billing_v1.js`
- `static/js/jom_admin_monitoring_v1.js`
- `static/js/jom_admin_system_configuration_v1.js`
- `static/js/jom_admin_users_access_v1.js`
- `static/js/jom_command_centre_completion_v1.js`
- `static/js/jom_estate_lifecycle_v1.js`
- `static/js/jom_estate_report_v1.js`
- `static/js/jom_executive_report_v1.js`
- `static/js/jom_governance_report_v1.js`
- `static/js/jom_lifecycle_decision_sync_v1.js`
- `static/js/jom_site_review_access_validation_v1.js`
- `static/js/jom_site_review_v1.js`
- `static/js/jom_site_workspace_shell_v1.js`
- `static/js/jom_site_workspace_v1.js`
- `templates/_nav.html`
- `templates/admin.html`
- `templates/admin_discovery.html`
- `templates/admin_estate_configuration.html`
- `templates/admin_licensing_billing.html`
- `templates/admin_monitoring.html`
- `templates/admin_system_configuration.html`
- `templates/admin_users_access.html`
- `templates/detail_list.html`
- `templates/estate.html`
- `templates/estate_report.html`
- `templates/executive_report.html`
- `templates/governance_configuration.html`
- `templates/governance_permissions.html`
- `templates/governance_policy_compliance.html`
- `templates/governance_projects.html`
- `templates/governance_report.html`
- `templates/governance_users.html`
- `templates/home.html`
- `templates/runtime_api.html`
- `templates/runtime_application.html`
- `templates/runtime_collectors.html`
- `templates/runtime_errors.html`
- `templates/runtime_jobs.html`
- `templates/runtime_status.html`
- `templates/site.html`
- `templates/site_review.html`
- `templates/site_workspace.html`
- `templates/source_authentication.html`
- `templates/source_completeness.html`
- `templates/source_connections.html`
- `templates/source_failures.html`
- `templates/source_freshness.html`
- `templates/source_health.html`

# Appendix E. Change History

- * 29d1166 (HEAD -> main, origin/main, origin/HEAD) Add actionable Users and Access drill-downs
- * 54f1c9a Add Users and Access named user drill-down UI
- * 4bc3984 Add Phase 1 named user drill-down endpoint
- * 33160f5 Add named user display identity authority
- * 5e91ab2 Integrate verified active Jira users into Users Access
- * 5052045 Add verified active Jira users authority
- * 99f1ad9 Correct Users Access product assignment authority
- * 06437f7 Remove duplicate Users Access rail limitations
- * 0ddbbb2 Add named site access authority source
- * 794bf8f Add aggregate site-level access authority
- * c173ddc Refine Users Access authority presentation
- * 399b306 Add aggregate user footprint to Users Access
- * ac2c2d1 Add administrative access authority to Users Access
- * 78c8537 Align Users Access UI with live account authority
- * a146a37 Integrate Users Access account authority and monitoring reliability
- * 804c2e4 Complete live Monitoring health refresh alignment
- * 81c5b8f Fix monitoring authority, group expansion, source freshness and named access reconciliation
- * 371048f fix product access refresh module execution
- * fe141e6 add governance report authority view
- * 82c9304 add estate report authority view
- * 6dd0ef2 update continuous improvement register
- * 1314695 add executive report authority view
- * f9502e8 add admin system configuration authority view
- * 9423890 add admin monitoring authority view
- * 50cc29b add admin users access authority view
- * 1c28103 add admin licensing billing authority view
- * 98948e2 add oauth-only page shells and navigation structure
- * 59591f3 cleanup: delete reviewed runtime removal candidates
- * 82dcad8 refactor: replace final reviewed runtime output marker
- * 5ca1926 refactor: replace remaining reviewed runtime output references
- * 8b4bc55 refactor: replace reviewed runtime output references
- * 2e723d4 refactor: neutralise runtime legacy markers
- * 7e4b8f2 refactor: neutralise legacy snapshot backup references
- * 8d34620 cleanup: retire scheduled sync scripts
- * 5de1674 refactor: remove scheduled sync references
- * 223b773 fix: separate headline users from product access assignments
- * a649aa5 Add Site Workspace product users metric
- * 55a2ee2 Correct Site Workspace main landing page
- * 722a929 Align Site Workspace overview metrics to runtime sources
- * 02df30a Consolidate Site Workspace route ownership
- * a6609ad Add live Command Centre NOC topology display
- * 3e0e15f Fix Estate render authority and validate stop monitoring lifecycle
- * 673cb9a Fix Estate render authority and validate stop monitoring lifecycle
- * f322fc3 Persist gli-tracker monitoring lifecycle completion
- * b5a7b44 Close Site Review lifecycle flow and audit record polish
- * 44f841b Show Site Review authorization action when access is required
- * 806e971 Remove Site Review route wrapper indirection
- * bdb9bd2 Remove obsolete runtime live truth status references
- * c6b5c44 Remove retired Admin warning actions from Command Centre
- * 6363e7b Reset estate current-state authority to live OAuth runtime scope
- * 7e4322a Guard initial Site Review lifecycle visibility
- * 773878b Guard enable monitoring to selected site
- * 5abbc80 Polish Site Review loading skeleton
- * cc3f84d Repair OAuth estate truth ownership
- * 3e558d5 Align Site Review access gate to current OAuth coverage
- * e05cb60 Consolidate Site Review lifecycle owner logic
- * 9e86aa9 Add Site Workspace shell and repair OAuth monitoring flow
- * eb6fa7b Polish Estate layout and rail presentation
- * 92e6ec4 Add conditional Estate lifecycle queues
- * c117856 Reduce Site Review access validation refresh repaint
- * e778f7c correct site review rail spacing and lifecycle controls
- * b61bf8a restore site review warning tile and hide decision help text
- * 5beba9a standardise active page layouts
- * 8ab0b2b retire admin UI and remove legacy frontend blockers
- * 16978a2 standardise JOM button sizing and estate table actions
- * 750e855 align estate table column widths
- * cdcd52f replace estate with single owner table renderer
- * 9b8bc7e polish site review visual wording and rail spacing
- * 05b61d1 gate site review oauth modal behind operator action
- * dba2a54 align site review lifecycle action controls
- * 3ffccf1 align command centre estate metrics to authenticated display model
- * 5fa61dd clean estate open site button encoding
- * 773cfd3 filter estate registry table to monitored authenticated sites
- * 5405607 enforce estate existing ui authenticated display filters
- * 26557d7 align estate workspace truth and restore estate frontend
- * f83a7a9 harden command centre release readiness checks
- * 9712af7 refine command centre rail and live action cards
- * 4a0a33e clean command centre live action cards and rail metrics
- * a566297 deduplicate command centre action alerts
- * 500600d add live organisation discovery to command centre contract
- * 592dea0 prefer admin api key for organisation discovery
- * 5b48a3a audit organisation discovery token source handling
- * 6b16fde align estate lifecycle authority runtime truth
- * 70963a5 remove retired migration scripts
- * ea4c123 remove retired audit utilities
- * f70d199 remove retired migration and validation scripts
- * 27aeca7 remove retired audit tooling
- * 158f79b refresh runtime estate access truth outputs
- * b62c04f refresh runtime estate and organisation truth outputs
- * c3ec8a3 runtime truth refresh and repository hygiene cleanup
- * 70c1b78 organisation discovery live source completion
- * 20abd2b backend live truth closeout and static truth remediation
- * f5d9365 populate live mapped estate admin contacts
- * ccf335a add estate site tenant identity mapping
- * d0ab537 add live site admin ownership collector
- * c9c88bc remediate drilldown and admin legacy runtime references
- * 90dd95c validate estate demo readiness
- * 4a31164 rebuild estate frontend single owner
- * 76abcfb align estate workspace contract shape
- * 166634b validate estate workspace contract route
- * ceb509c replace estate runtime legacy consumers
- * d486993 audit estate single owner blueprint
- * 6a8eac4 cleanup legacy runtime contract references
- * d7eb846 repair backend static truth references
- * 7f22217 remove active static data path ownership references
- * 9de86a4 wire estate discovery authority coverage frontend
- * 924687f remove frontend static data reference
- * 7cffbb9 add estate discovery authority coverage route
- * 3943455 fix runtime guarded JSON serialization
- * 742a564 remove runtime static data fallback resolver
- * b4a5831 remove static data fallback files
- * c0d7f75 relocate runtime data to runtime path
- * 36dd5ee add runtime data path abstraction
- * fe30602 remove repository debris and static status markers
- * efdc9e0 align estate operational and site review truth sources
- * c781294 align command centre estate truth and remove duplicate lifecycle action
- * 56ee006 repair estate validate access oauth flow
- * bdbfbc6 remove estate cleanup and validation status artifacts
- * ea46faf fix estate monitored source and render gate
- * e6403e5 align estate manage actions to site review flow
- * 73ac5af complete estate monitored registry and manage flow
- * 25d75c3 complete estate core rendering and registry cleanup
- * 33cab19 clean estate owner css hidden rules
- * b61d18b remove estate cleanup frontend layers
- * 98eecc6 rebuild command centre attention workflow
- * a25e157 rebuild command centre single owner frontend
- * 9d9daa9 isolate command centre frontend ownership
- * 553e0a5 expose command centre users metric in workspace contract
- * b5a5a1c stabilise command centre action and coverage rendering
- * 3bc67ce fix command centre workspace payload rendering
- * 6ff150c fast render workspace page routes
- * a81a134 refresh estate truth outputs
- * 5834f13 cache workspace contracts for faster page loads
- * 7cea5b6 consolidate command centre workspace contract
- * ff4291b consolidate command centre live data bindings
- * 402df58 refresh generated estate truth outputs
- * 864dc8c align command centre users metric to live product access
- * 04dd264 repair user footprint summary and command centre status display
- * 5c813c7 fix command centre rail truth display bindings
- * 119ff65 connect estate widgets to backend contracts
- * 00a9d95 connect command centre widgets to live contracts
- * 61ef230 isolate operational scripts from website truth audit
- * a7ffebc add frontend reconnect audit status
- * eda2e69 full
- * ed78888 refresh generated backend truth outputs
- * aa770e2 remove final legacy website truth references
- * 0058e37 refresh generated backend truth outputs
- * 0301317 eradicate backend legacy website truth inputs
- * ee6ac5d audit final backend truth chain legacy inputs
- * 17b56ed enforce backend live truth sources
- * 84a18db repair operator route runtime chain
- * 5fb77e4 remove named access literal static artifacts
- * bd931a2 restore live site review contract helper
- * e3b866b remove operational console static artifacts
- * a2b15cc Revert "remove operational console static artifacts"
- * 2fbf355 remove operational console static artifacts
- * db0a78b replace referenced artifact routes with live contracts
- * c04a46a align site workspace live contract display
- * 1d47ba1 remove site workspace static truth reads
- * 646668e repair runtime chain and remove stale unreferenced artifacts
- * abb5ae2 add runtime live truth status and snapshot demotion
- * 1a4b4fa align registry contracts and live truth sources
- * b090d6a restore live product access and add oauth onboarding gate
- * c7940b5 (agents/try-it-now-feature, agents/project-structure-mapping-exploration-b0731599) full
- * f5e2ce9 (agents/verify-functionality-checks, agents/project-structure-mapping-exploration) refresh site runtime data after consolidation
- * 3cc7d20 remove unused program files
- * 9166d3d merge site workspace source and remove overlay layers
- * c14d0f5 clean duplicate site workspace navigation
- * eaf14b6 full
- * 04c4b69 clean estate lifecycle navigation and site review workflow
- * 803dcc7 add estate site review lifecycle validation and monitoring flow
- * dd89455 full
- * 5feef15 full
- * 34899aa lock command centre operations rail layout
- * e3e3c19 finalise command centre and estate lifecycle workflow
- * ef3eda7 full
- * 3d4ea4c finalise command centre review item wording
- * 10cc79b repair command centre operational truth and reporting runtime source
- * a79b6d9 full
- * eeec3aa freeze command centre final layout and remove old experiment layers
- * 6428676 simplify command centre operational workflow
- * 061a65f repair command centre rationalised rendering
- * 8e6c4f9 rationalise command centre workflow v4
- * e6223b4 add executive intelligence and trend analytics
- * 8c93f0a add executive demo and reporting enhancement v2
- * b6a2c97 (tag: production-candidate-v2-demo-ready) add release candidate demo prep and tagging guide
- * 555d1d7 expand command centre intelligence and admin governance depth
- * be9d2ed rebuild navigation architecture and restore branding
- * eddd007 implement export and reporting framework v1
- * 1e65c19 (tag: production-candidate-v2-hardening-v1) add production candidate hardening plus pack
- * 00ebfc6 add executive demo and reporting pack
- * c30aca3 add production candidate closeout v2 documentation
- * bdebba2 align admin discovery queue with registry monitoring state
- * b54bf83 full
- * 3a74934 add production candidate documentation and release guidance
- * 2eefdf4 add end of month production readiness documentation
- * 24988e6 add operational readiness layer across core workspaces
- * 4104ebd add visual consistency layer across core workspaces
- * 4d3c721 remove duplicate command centre intelligence block
- * 9bf5f34 expand admin workspace into intelligence centre

# Estate Configuration Authority Milestone

**Validation date:** 14 August 2026
**Implementation status:** Live validated, pending BOOKSYNC commit
**Authority contract:** `jom-admin-estate-configuration-authority-v1`
**Page:** `/admin/estate-configuration`
**API:** `/api/admin/estate-configuration`

### Validated authority

- Estate sites: 4
- Monitored sites: 4
- Tenant identity: 4 sites, 100% coverage
- Resource mapping: 3 sites, 75% coverage
- Administrative ownership: 3 sites, 75% coverage
- Verified role assignments: 97
- Authority gaps: 7
- Failed sources: 0
- Live collection during page load: disabled

### Site-level authority

- `gli-delivery-tm`: tenant identity available; resource mapping available; ownership available; 13 Jira Software role assignments.
- `gli-global-technology`: tenant identity available; resource mapping available; ownership available; 29 Jira Software role assignments.
- `gli-it-project`: tenant identity available; resource mapping available; ownership available; 55 role assignments across Confluence and Jira Software.
- `gli-tracker`: tenant identity available; resource mapping unavailable; ownership unavailable; assignment count and products unavailable.

### Configuration gaps

1. Business classification is unavailable. The existing `classification` field represents monitoring lifecycle rather than proven business classification.
2. Criticality is unavailable.
3. Region is unavailable.
4. Business unit is unavailable.
5. Tags are unavailable.
6. Resource mapping coverage is partial because `gli-tracker` has tenant identity but no proven product-resource mapping.
7. Administrative ownership coverage is partial because `gli-tracker` has no safe mapped resource and verified role-assignment evidence.

### Authority sources

- `runtime/data/site_registry.json`
- `runtime/data/estate_admin_site_inventory_v1.json`
- `runtime/data/estate_discovery_authority_v1.json`
- `runtime/data/estate_admin_contacts_v1.json`
- `runtime/data/estate_site_resource_mapping_v1.json`
- `runtime/data/estate_site_tenant_identity_v1.json`

### Owner files

- `app/web.py`
- `templates/admin_estate_configuration.html`
- `static/js/jom_admin_estate_configuration_v1.js`
- `static/css/jom_admin_estate_configuration_v1.css`
- `scripts/validate_estate_configuration_v1.py`

### Truth and privacy controls

- The page composes current runtime, OAuth and Admin authority only.
- No collector runs during page load.
- Missing ownership is reported as unavailable, not zero.
- Role-assignment counts are not represented as unique people.
- Names, email addresses, account IDs and directory IDs are excluded from the page contract.
- Differing source evidence timestamps remain visible.

## Estate Configuration, completed authority v3

**Acceptance date:** 17 August 2026
**Status:** Completed and accepted, pending BOOKSYNC milestone commit
**Runtime status:** `ok_with_limitations`

Estate Configuration is the estate-wide inventory of monitored sites, proven monitored products, Marketplace App authority state and aggregate administrative ownership. Estate remains the monitored site registry and lifecycle view. Site Workspace remains the selected-site drill-down. Licensing & Billing remains the separate commercial entitlement, subscription and cost view.

### Accepted live evidence
- 4 monitored sites.
- 2 unique monitored products: Confluence and Jira Software.
- 6 proven site-product assignments.
- 4 product-covered sites and 100% product coverage.
- 4 ownership-covered sites, 33 current role-assignment rows and 100% ownership coverage.
- 0 failed sources and 0 blocking actions.
- Marketplace App count is unavailable, not zero.

### Current site evidence
- `gli-delivery-tm`: Confluence and Jira Software; Marketplace Apps unavailable; ownership available; 14 assignments.
- `gli-global-technology`: Jira Software; Marketplace Apps unavailable; ownership available; 2 assignments.
- `gli-it-project`: Confluence and Jira Software; Marketplace Apps unavailable; ownership available; 13 assignments.
- `gli-tracker`: Jira Software; Marketplace Apps unavailable; ownership available; 4 assignments.

The API summary total, site-row sum, authority summary, actual authority rows and grouped authority rows were reconciled at 33. The accepted `estate_admin_contacts_v1.json` evidence was generated at `2026-08-17T12:26:28Z`. Earlier totals are superseded rather than silently preserved.

### Connected Apps limitation
Atlassian Administration exposed two meaningful Jira gateway candidates in authenticated browser evidence: the full plugins endpoint and `installed-marketplace`. Browser responses returned HTTP 200 and both shapes reported 204 rows. Equal counts did not prove Marketplace-only filtering, installation semantics, system-app exclusion, pagination or completeness.

A privacy-safe non-browser audit tested four monitored sites, two endpoints and two configured authentication modes, producing 16 probes. Admin Bearer returned eight HTTP 406 responses. OAuth Bearer returned eight HTTP 401 responses. Successful probes were zero. Confluence authority was not proven. JOM therefore records Marketplace Apps as unavailable, provides an Atlassian Administration review action and keeps `safe_to_publish_marketplace_apps` false. Browser cookies and private session automation are not accepted collector authority.

### Owner map
- Backend and route: `app/web.py`
- Page: `templates/admin_estate_configuration.html`
- Browser owner: `static/js/jom_admin_estate_configuration_v1.js`
- Styling owner: `static/css/jom_admin_estate_configuration_v1.css`
- Administrative ownership builder: `app/builders/estate_admin_contacts.py`
- Resource authority builder: `app/builders/estate_resource_authority.py`
- Monitored product builder: `app/builders/estate_monitored_product_authority.py`
- Marketplace limitation builder: `app/builders/estate_marketplace_app_authority.py`
- Post-approval chain: `app/runtime/admin_enriched_chain.py`

### Runtime contracts
- `runtime/data/site_registry.json`
- `runtime/data/estate_site_resource_mapping_v1.json`
- `runtime/data/estate_admin_contacts_v1.json`
- `runtime/data/estate_monitored_product_authority_v1.json`
- `runtime/data/estate_marketplace_app_authority_v1.json`
- `runtime/data/estate_resource_authority_refresh_status_v1.json`

### Discovery and audit owners
- `app/audits/connected_apps_authority_discovery.py`
- `app/audits/connected_apps_discovery_privacy_correction.py`
- `app/audits/jira_connected_apps_endpoint_contract_audit.py`
- `app/audits/marketplace_app_authority_discovery.py`

### Validation evidence
The lifecycle, API v3, compact UI, resource ARI, monitored product and Marketplace limitation validators passed. `app/web.py` and relevant builders compiled. The health endpoint returned healthy. API v3 returned `ok_with_limitations`. Live totals reconciled. Visual review accepted the compact product chips, separate Marketplace and ownership columns, single-location limitation explanation, aligned actions and unobstructed rails. `git diff --check` returned line-ending warnings only and no whitespace defect.

### Continuation rule
Do not repeat the completed Estate Configuration authority audit after a chat reset unless new runtime evidence, a failed validator or a changed owner creates a real reason. Resume with repository status, current branch and HEAD, validate the staged milestone, commit and push. Only then select the next incomplete Admin page. Preserve the audit-first rules: evidence first, unavailable means unavailable, no fabricated authority, full owner replacements, repository hygiene and BOOKSYNC with every milestone.
