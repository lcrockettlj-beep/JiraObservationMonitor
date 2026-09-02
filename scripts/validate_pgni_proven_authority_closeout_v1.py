from pathlib import Path
import ast,json,sys
root=Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name=='scripts' else Path.cwd()
if str(root) not in sys.path: sys.path.insert(0,str(root))
guide=root/'JOM Living Guide'
markdown=['BOOKSYNC Guide.md','JOM Change History.md','JOM Progress and Improvements.md','JOM Quick Start.md','JOM Recovery Guide.md','JOM System and File Map.md','The Jira Observation Monitor Guide.md']
markers=['Project Governance Named Identity Authority v1 proven closeout','status `ok`','capability state `PROVEN`','67 named governance principals','270 supported governance assignments','100.0% project-detail coverage','100.0% role-detail coverage','Organisation administrator','supersede the earlier partial run']
for name in markdown:
 text=(guide/name).read_text(encoding='utf-8-sig')
 for marker in markers: assert marker in text,(name,marker)
record=json.loads((guide/'GitHub Repository Record.json').read_text(encoding='utf-8-sig'))['pgni_booksync']
assert record['authority_status']=='ok' and record['capability_state']=='PROVEN' and record['safe_to_serve'] is True
assert record['named_principals']==67 and record['assignment_count']==270 and record['request_failures']==0
assert record['project_coverage_percent']==100.0 and record['role_coverage_percent']==100.0
assert record['supersedes']['assignment_count']==281 and record['privacy']['account_ids_stored'] is False
contract=json.loads((root/'runtime/data/project_governance_named_identity_authority_v1.json').read_text(encoding='utf-8-sig')); q=contract.get('quality',{}); a=contract.get('authority',{}); status=contract.get('status')
assert status in {'ok','partial'} and a.get('safe_to_serve') is True and len(contract.get('identities',[]))>0
if status=='ok':
 assert q.get('capability_state')=='PROVEN' and q.get('full_success') is True and q.get('request_failures')==0 and q.get('project_coverage_percent')==100.0 and q.get('role_coverage_percent')==100.0
else:
 assert q.get('capability_state')=='PARTIAL' and q.get('publishable_with_recorded_exceptions') is True and q.get('project_coverage_percent',0)>=95 and q.get('role_coverage_percent',0)>=75
assert q.get('account_ids_stored') is False and q.get('email_stored') is False and q.get('raw_responses_stored') is False
from app.web import app
with app.test_client() as client:
 response=client.get('/api/governance/projects/named-identities',environ_base={'REMOTE_ADDR':'127.0.0.1'}); assert response.status_code==200,response.status_code; data=response.get_json(); assert data.get('status')=='ok' and len(data.get('identities',[]))>0; assert data.get('privacy',{}).get('account_id_exposed') is False and data.get('privacy',{}).get('email_exposed') is False
print('PASS: PGNI proven closeout BOOKSYNC, dual-state consumer, live authority, API, privacy and access boundaries validated.')
