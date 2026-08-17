from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
web=(root/'app/web.py').read_text(encoding='utf-8'); ast.parse(web)
html=(root/'templates/admin_estate_configuration.html').read_text(encoding='utf-8')
js=(root/'static/js/jom_admin_estate_configuration_v1.js').read_text(encoding='utf-8')
required_web=['jom-admin-estate-configuration-authority-v3','estate_monitored_product_authority_v1.json','estate_marketplace_app_authority_v1.json','/site-workspace/','marketplace_app_count','ok_with_limitations','No personal ownership records']
required_html=['Monitored Products','Marketplace Apps','Ownership Coverage','Products, apps and ownership','data-owner="JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3"']
required_js=['monitored_products','marketplace_apps','assignment_count','OK / LIMITATION','blocking_action_items']
for group,text in [(required_web,web),(required_html,html),(required_js,js)]:
 missing=[x for x in group if x not in text]; assert not missing,missing
block=web[web.index('# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 START ---'):web.index('# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 END ---')]
for forbidden in ['account_id', 'email', 'resource_id']:
 assert forbidden not in block,forbidden
print('PASS: Estate Configuration v3 products, Marketplace App limitation, ownership and Site Workspace integration validated.')
