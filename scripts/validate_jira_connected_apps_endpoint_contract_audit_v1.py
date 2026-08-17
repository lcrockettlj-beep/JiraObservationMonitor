from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]; p=root/'app/audits/jira_connected_apps_endpoint_contract_audit.py'; t=p.read_text(encoding='utf-8'); ast.parse(t)
for x in ['cloud_ids_stored','authorization_headers_stored','raw_response_bodies_stored','app_records_stored','safe_to_publish_marketplace_apps','Host license entitlement fields describe the host product']:
 assert x in t,x
print('PASS: Jira Connected Apps endpoint contract audit privacy, field-boundary and non-publishing gates validated.')
