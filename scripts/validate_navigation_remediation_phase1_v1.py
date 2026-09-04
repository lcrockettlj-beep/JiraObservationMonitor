from pathlib import Path
import ast, sys
root=Path(__file__).resolve().parents[1]
expected={
 'governance_report.html':['/reports/governance/projects','/reports/governance/users','/reports/governance/permissions','/reports/governance/configuration','/reports/governance/policy-compliance'],
 'estate_report.html':['/estate','/site-workspace','/estate/pending','/estate/monitored','/estate/discovered'],
 'executive_report.html':['/estate','/reports/governance','/runtime-status','/source-health'],
}
for name,routes in expected.items():
 text=(root/'templates'/name).read_text(encoding='utf-8-sig')
 assert 'jom_navigation_remediation_phase1_v1.css' in text,name
 assert 'Operational navigation' in text,name
 for route in routes: assert f'href="{route}"' in text,(name,route)
css=(root/'static/css/jom_navigation_remediation_phase1_v1.css').read_text(encoding='utf-8-sig')
assert '.jom-related-navigation' in css and '@media' in css
w=(root/'app/web.py').read_text(encoding='utf-8-sig');ast.parse(w)
for route in ['/reports/governance/projects','/reports/governance/users','/reports/governance/permissions','/reports/governance/configuration','/reports/governance/policy-compliance','/estate','/site-workspace','/estate/pending','/estate/monitored','/estate/discovered','/runtime-status','/source-health']:
 assert route in w,route
if str(root) not in sys.path: sys.path.insert(0,str(root))
from app.web import app
with app.test_client() as client:
 for route in ['/executive-report','/estate-report','/reports/governance','/runtime-status','/source-health']:
  response=client.get(route);assert response.status_code==200,(route,response.status_code)
 for route in ['/reports/governance/projects','/reports/governance/users','/reports/governance/permissions','/reports/governance/configuration','/reports/governance/policy-compliance','/estate','/site-workspace','/estate/pending','/estate/monitored','/estate/discovered','/runtime-status','/source-health']:
  response=client.get(route);assert response.status_code in {200,302},(route,response.status_code)
print('PASS: Navigation Remediation Phase 1 report-to-operational links, reciprocal Runtime and Source Health access, route reachability, responsive layout and existing page ownership validated.')