# Post-Expansion Validation Pack v1

- Repository: `C:\Users\Luke_C\Desktop\JiraObservationMonitor`
- Timestamp: `20260720_091953`
- Base URL: `http://127.0.0.1:5000`
- Decision: `PASS`

## Scope
Validates the expanded Command Centre, Estate, Admin Governance Depth, Site Workspace, Reporting Framework, navigation state, retained compatibility routes and active frontend asset stack after the recent expansion packs.

## Readiness Scores
|Area|Score|
|---|---|
|frontend_route_readiness|100.0%|
|endpoint_readiness|100.0%|
|asset_readiness|100.0%|
|marker_readiness|100.0%|
|orphan_cleanup_readiness|100.0%|
|overall_readiness|100.0%|

## Route Validation
|Route|Status|OK|Bytes|Error|
|---|---|---|---|---|
|/|200|True|11495||
|/estate|200|True|8345||
|/reference|200|True|11426||
|/site/gli-it-project|200|True|6434||
|/site/gli-delivery-tm|200|True|6435||
|/site/gli-global-technology|200|True|6441||

## Endpoint Validation
|Endpoint|Status|OK|Bytes|Error|
|---|---|---|---|---|
|/operator/summary|200|True|1281||
|/operator/alerts|200|True|359||
|/operator/surface|200|True|64488||
|/operator/observability|200|True|508||
|/registry/sites|200|True|5452||
|/estate/product-access|200|True|5067||
|/users/footprint|200|True|48161||
|/admin/truth|200|True|4913||
|/api/data|200|True|139399||
|/api/source-state|200|True|8290||
|/api/site-registry|200|True|5452||
|/reports/generated/executive/html|200|True|1204||
|/reports/generated/executive/json|200|True|362||
|/reports/generated/executive/csv|200|True|313||
|/reports/generated/estate/html|200|True|3384||
|/reports/generated/estate/json|200|True|1828||
|/reports/generated/estate/csv|200|True|1634||
|/reports/generated/admin/html|200|True|2284||
|/reports/generated/admin/json|200|True|1130||
|/reports/generated/admin/csv|200|True|1006||

## Static Asset Validation
|Asset|Status|OK|Bytes|Error|
|---|---|---|---|---|
|/static/css/jom_atlassian_command.css|200|True|14758||
|/static/css/jom_visual_consistency_v2.css|200|True|4429||
|/static/css/jom_operational_readiness_v1.css|200|True|2528||
|/static/css/jom_export_reporting_v1.css|200|True|413||
|/static/css/jom_admin_workspace_v2.css|200|True|4672||
|/static/css/jom_admin_governance_depth_v1.css|200|True|3097||
|/static/css/jom_site_workspace_v1.css|200|True|7221||
|/static/css/jom_home_command_intelligence_v2.css|200|True|3329||
|/static/js/jom_command_centre.js|200|True|16553||
|/static/js/jom_operational_readiness_v1.js|200|True|4742||
|/static/js/jom_export_reporting_v1.js|200|True|1483||
|/static/js/jom_admin_workspace_v2.js|200|True|10402||
|/static/js/jom_admin_governance_depth_v1.js|200|True|7366||
|/static/js/jom_site_workspace_v1.js|200|True|20376||
|/static/js/jom_home_command_intelligence_v2.js|200|True|7058||

## Workspace Marker Checks
|File|Marker|Found|
|---|---|---|
|templates/home.html|command-intelligence-v2|True|
|templates/home.html|command-v2-health-score|True|
|templates/home.html|command-v2-risk-list|True|
|templates/home.html|command-v2-action-list|True|
|templates/home.html|command-v2-event-list|True|
|templates/home.html|jom_home_command_intelligence_v2.js|True|
|templates/home.html|Discovery Queue|True|
|templates/home.html|Runtime Diagnostics|True|
|templates/reference.html|Admin Intelligence Centre|True|
|templates/reference.html|admin-governance-depth-v1|True|
|templates/reference.html|admin-gov-posture|True|
|templates/reference.html|admin-gov-discovery-table|True|
|templates/reference.html|admin-gov-action-list|True|
|templates/reference.html|jom_admin_workspace_v2.js|True|
|templates/reference.html|jom_admin_governance_depth_v1.js|True|
|templates/estate.html|Estate Table|True|
|templates/estate.html|estate-site-body|True|
|templates/estate.html|jom_command_centre.js|True|
|templates/estate.html|jom_export_reporting_v1.js|True|
|templates/site.html|Site Workspace|True|
|templates/site.html|site-signal-list|True|
|templates/site.html|Developer diagnostics|True|
|templates/site.html|jom_site_workspace_v1.js|True|

## Risk Marker Checks
|File|Marker|Count|
|---|---|---|
|templates/home.html|JOM_HOME_COMMAND_INTELLIGENCE_V1_START|0|
|templates/reference.html|Admin Foundation Build v1|0|
|templates/reference.html|site-discovery-control|0|
|templates/site.html|Loading signals...|0|
|templates/site.html|MutationObserver|0|
|static/js/jom_site_workspace_v1.js|MutationObserver|0|
|static/js/jom_site_workspace_v1.js|Loading signals...|0|

## Orphan/Stale Asset Checks
|File|Exists|
|---|---|
|static/css/jom_admin_workspace_v1.css|False|
|static/js/jom_admin_workspace_v1.js|False|
|static/css/jom_layout_shell_v1.css|False|
|static/js/jom_layout_shell_v1.js|False|
|static/css/jom_operator_experience_v1.css|False|
|static/js/jom_operator_experience_v1.js|False|
|static/css/jom_sidebar_layout_repair_v1.css|False|
|static/css/jom_command_colour_alignment_v1.css|False|
|static/css/jom_nav_font_identity_v1.css|False|
|static/css/jom_home_command_intelligence_v1.css|False|
|static/js/jom_home_command_intelligence_v1.js|False|

## Documentation Checkpoints
|File|Exists|
|---|---|
|docs/production_candidate_closeout_v2/PRODUCTION_CANDIDATE_CLOSEOUT_V2.md|True|
|docs/executive_demo_reporting_v1/EXECUTIVE_DEMO_BRIEF_V1.md|True|
|docs/production_candidate_hardening_plus_v1/PRODUCTION_CANDIDATE_HARDENING_REPORT_V1.md|True|
|docs/admin_governance_depth_v1/ADMIN_GOVERNANCE_DEPTH_V1.md|True|
|docs/home_command_centre_intelligence_v2/HOME_COMMAND_CENTRE_INTELLIGENCE_EXPANSION_V2.md|True|

## Issues
- None

## Warnings
- None

## Git Status After Validation
```text
(clean)
```

## Files Generated
- `POST_EXPANSION_VALIDATION_SUMMARY.md`
- `route_results.json`
- `endpoint_results.json`
- `asset_results.json`
- `marker_results.json`
- `risk_marker_results.json`
- `orphan_results.json`
- `doc_check_results.json`
- `readiness_scores.json`
- `post_expansion_validation_matrix.csv`
- `git_status.txt`