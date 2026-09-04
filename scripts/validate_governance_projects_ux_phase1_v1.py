from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[1]
if str(root) not in sys.path:sys.path.insert(0,str(root))
html=(root/'templates/governance_projects.html').read_text(encoding='utf-8-sig')
js=(root/'static/js/jom_governance_projects_v1.js').read_text(encoding='utf-8-sig')
css=(root/'static/css/jom_governance_projects_v1.css').read_text(encoding='utf-8-sig')
for marker in ['gp-summary-projects','gp-summary-owned','gp-summary-coverage','gp-summary-gaps','gp-summary-distinct','gp-governance-rows','gp-owner-view','Project Lead is the GLI Space Owner','Jira does not provide a native Project Owner field'] : assert marker in html,marker
for marker in ['/api/governance/projects','/api/governance/projects/leads','/api/governance/projects/owners','Project authorities are not synchronized','owner_coverage_percent','governance_state','renderOwners'] : assert marker in js,marker
for marker in ['gp__summary','gp__summary-gap','gp__provenance','gp__owner-grid','gp__state--gap','@media(max-width:650px)'] : assert marker in css,marker
assert 'account_id' not in js and 'email' not in js and 'innerHTML' not in js
from app.web import app
with app.test_client() as c:
 page=c.get('/reports/governance/projects');assert page.status_code==200;body=page.get_data(as_text=True);assert 'gp-governance-rows' in body and 'gp-owner-view' in body
 for route in ['/api/governance/projects','/api/governance/projects/leads','/api/governance/projects/owners']:
  r=c.get(route,environ_base={'REMOTE_ADDR':'127.0.0.1'});assert r.status_code==200,(route,r.status_code);d=r.get_json();assert d
 owner=c.get('/api/governance/projects/owners',environ_base={'REMOTE_ADDR':'127.0.0.1'}).get_json();assert owner['privacy']['account_id_exposed'] is False and owner['privacy']['email_exposed'] is False and owner['definition']['native_jira_owner_field_present'] is False
 assert c.get('/api/governance/projects/owners',environ_base={'REMOTE_ADDR':'192.0.2.1'}).status_code==403
print('PASS: Governance Projects UX Phase 1 summary, project-centric grid, gap filter, owner relationships, provenance, responsive layout, API and privacy gates validated.')
