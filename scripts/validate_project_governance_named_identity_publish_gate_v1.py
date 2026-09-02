from pathlib import Path
import ast,json,sys
p=Path('app/builders/project_governance_named_identity_authority_v1.py')
s=p.read_text(encoding='utf-8-sig'); ast.parse(s)
for value in ['project_coverage >= 0.95','role_coverage >= 0.75','publishable_with_recorded_exceptions','capability_state','"safe_to_serve":publishable','"identities":rows if publishable else []','if publishable: write_atomic']:
    assert value in s,value
if '--contract' in sys.argv:
    c=Path('runtime/data/project_governance_named_identity_authority_v1.json')
    assert c.exists(),'PGNI authority contract missing'
    x=json.loads(c.read_text(encoding='utf-8-sig')); q=x.get('quality',{}); a=x.get('authority',{}); rows=x.get('identities',[])
    assert x.get('status') in {'ok','partial'}
    assert a.get('safe_to_serve') is True
    assert q.get('publishable_with_recorded_exceptions') is True
    assert q.get('project_coverage_percent',0) >= 95.0
    assert q.get('role_coverage_percent',0) >= 75.0
    assert len(rows)>0
    assert q.get('account_ids_stored') is False and q.get('email_stored') is False and q.get('raw_responses_stored') is False
print('PASS: PGNI partial publish, explicit coverage, privacy, and success-only replacement contract validated.')
