from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
web=(root/'app/web.py').read_text(encoding='utf-8'); ast.parse(web)
checks={
'app/web.py':['/api/admin/estate-configuration','jom-admin-estate-configuration-authority-v1','privacy_policy'],
'templates/admin_estate_configuration.html':['jom_admin_estate_configuration_v1.css','jom_admin_estate_configuration_v1.js','ec-site-rows'],
'static/js/jom_admin_estate_configuration_v1.js':['/api/admin/estate-configuration','ec-ownership','ec-gaps'],
'static/css/jom_admin_estate_configuration_v1.css':['admin-estate-configuration','.estate-rail']};
for rel,needles in checks.items():
 text=(root/rel).read_text(encoding='utf-8'); missing=[n for n in needles if n not in text]; assert not missing,(rel,missing)
owner=web[web.index('# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V1 START ---'):web.index('# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V1 END ---')]
assert 'row.get("email")' not in owner and 'row.get("account_id")' not in owner and 'row.get("directory_id")' not in owner
print('PASS: Estate Configuration owner files, route, privacy boundary and Python syntax validated.')
