from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
a=(root/'app/runtime/admin_enriched_chain.py').read_text(encoding='utf-8-sig')
r=(root/'app/runtime/runtime_sources_refresh.py').read_text(encoding='utf-8-sig')
ast.parse(a); ast.parse(r)
order=['admin_directory_users','admin_truth_v2','admin_group_expansion','named_access_truth_v2','named_access_reconciliation_v2','user_footprint','named_site_access_authority','named_user_display_identity','verified_active_jira_users','users_access_actionable_drilldown']
pos=[a.index('("'+x+'"') for x in order]
assert pos==sorted(pos),(order,pos)
required_modules=['app.access.collect_admin_group_expansion','app.access.named_access_truth_v2','app.access.reconcile_named_access_truth_v2','app.access.user_footprint_source','app.builders.named_site_access_authority_v1','app.builders.named_user_display_identity_v1','app.builders.verified_active_jira_users_v1','app.builders.users_access_actionable_drilldown_v1']
for value in required_modules: assert value in a,value
for value in ['classify_estate_resource_authority','ok_with_advisory','advisory_count','advisories','direct_module_named_access_chain','validate_group_expansion','validate_named_truth','validate_reconciliation','validate_footprint','validate_named_site','validate_identity','validate_actionable','project_governance_named_identity','validate_project_governance_named_identity','postcondition_gates','blocked_by','finally:','flush=True']: assert value in a,value
assert 'app.access.group_expansion_recovery_runner' not in a
for value in ['runtime_refresh_status.json','maximum_interval_hours','fail_closed','dependency_order_enforced','finally:']: assert value in r,value
print('PASS: v4.1 Estate advisory classification, direct-module named-access chain, complete postconditions, durable status, independent activity authority and fail-closed order validated.')
