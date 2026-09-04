from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
if str(root) not in sys.path:sys.path.insert(0,str(root))
h=(root/'templates/governance_projects.html').read_text(encoding='utf-8-sig');j=(root/'static/js/jom_governance_projects_v1.js').read_text(encoding='utf-8-sig');c=(root/'static/css/jom_governance_projects_v1.css').read_text(encoding='utf-8-sig')
for x in ['gp-gaps','gp-gap-grid','gp-drawer','gp-owner-sort','gp-owner-filter','gp-health-grid','gp-clear','Project Lead is the GLI Space Owner','Native Jira owner field'] : assert x in h+j,x
for x in ['renderGaps','openDrawer','closeDrawer','renderHealth','Filter projects','Project authorities are not synchronized','owner_coverage_percent','Escape'] : assert x in j,x
for x in ['gp__drawer[aria-hidden="false"]','gp__backdrop','gp__health-grid','gp__gap-grid','gp__jump','@media(max-width:650px)'] : assert x in c,x
assert 'innerHTML' not in j and 'account_id' not in j and 'email' not in j
from app.web import app
with app.test_client() as client:
 p=client.get('/reports/governance/projects');assert p.status_code==200;body=p.get_data(as_text=True);assert 'gp-drawer' in body and 'gp-health-grid' in body and 'gp-gap-grid' in body
 for route in ['/api/governance/projects','/api/governance/projects/leads','/api/governance/projects/owners']:
  r=client.get(route,environ_base={'REMOTE_ADDR':'127.0.0.1'});assert r.status_code==200,(route,r.status_code)
 assert client.get('/api/governance/projects/owners',environ_base={'REMOTE_ADDR':'192.0.2.1'}).status_code==403
print('PASS: Governance Projects UX Phase 2 gap dashboard, project drawer, owner relationship controls, authority health, quick navigation, synchronization and privacy gates validated.')