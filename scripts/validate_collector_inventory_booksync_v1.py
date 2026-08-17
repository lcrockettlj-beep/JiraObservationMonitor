from pathlib import Path
import json, sys
root=Path(__file__).resolve().parents[1]
owners=[
"BOOKSYNC Guide.md","JOM Change History.md","JOM Progress and Improvements.md",
"JOM Quick Start.md","JOM Recovery Guide.md","JOM System and File Map.md",
"The Jira Observation Monitor Guide.md"]
base=root/'JOM Living Guide'
needle='Collector Inventory Authority Audit, 17 August 2026'
for name in owners:
    p=base/name
    assert p.exists(), f'missing {p}'
    text=p.read_text(encoding='utf-8-sig')
    assert text.count(needle)==1, f'{name}: expected exactly one collector inventory section'
    for required in ['admin_named_access_endpoint_probe.py','collect_admin_group_expansion.py','estate_product_access.py','verified_active_jira_users_v1.py','Marketplace App Authority Build']:
        assert required in text, f'{name}: missing {required}'
record=json.loads((base/'GitHub Repository Record.json').read_text(encoding='utf-8-sig'))
entry=record.get('collector_inventory_audit') or {}
assert entry.get('evidence_file')=='JOM_Collector_Audit.txt'
assert entry.get('current_workstream')=='Marketplace App Authority Build'
assert entry.get('marketplace_app_authority')=='unavailable_pending_supported_collector'
assert (root/'JOM_Collector_Audit.txt').exists(), 'audit evidence not present at repository root'
print('PASS: Collector Inventory BOOKSYNC evidence, owner catalogue, continuity and Marketplace workstream validated.')
