from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
files=[root/'app/web.py',root/'app/builders/estate_resource_authority.py',root/'app/builders/estate_admin_contacts.py',root/'app/runtime/admin_enriched_chain.py']
for path in files: ast.parse(path.read_text(encoding='utf-8'))
checks={
'app/web.py':['jom-admin-estate-configuration-authority-v3','automatic_post_approval_refresh','_jom_estate_post_approval_authority_refresh_v1'],
'app/builders/estate_resource_authority.py':['current monitored tenant cloud_id','ambiguous_role_rows','ACCEPTED_PRODUCTS'],
'app/runtime/admin_enriched_chain.py':['app.builders.estate_resource_authority'],
'templates/admin_estate_configuration.html':['ec-actions','JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3'],
'static/js/jom_admin_estate_configuration_v1.js':['ec-rail-actions','No configuration actions']};
for rel,needles in checks.items():
 text=(root/rel).read_text(encoding='utf-8'); missing=[n for n in needles if n not in text]; assert not missing,(rel,missing)
web=(root/'app/web.py').read_text(encoding='utf-8'); owner=web[web.index('# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 START ---'):web.index('# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 END ---')]
for forbidden in ['row.get("email")','row.get("account_id")','row.get("directory_id")','resource_id":']:
 assert forbidden not in owner,forbidden
assert 'Business classification' not in owner and 'Criticality' not in owner and 'Business unit' not in owner
print('PASS: Estate Configuration lifecycle completion owners, privacy boundary and Python syntax validated.')
