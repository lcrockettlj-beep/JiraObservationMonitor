from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
web=(root/'app/web.py').read_text(encoding='utf-8'); ast.parse(web)
html=(root/'templates/admin_estate_configuration.html').read_text(encoding='utf-8')
js=(root/'static/js/jom_admin_estate_configuration_v1.js').read_text(encoding='utf-8')
css=(root/'static/css/jom_admin_estate_configuration_v1.css').read_text(encoding='utf-8')
assert 'jom-admin-estate-configuration-authority-v3' in web
for item in ['ec-products-note','ec-ownership-note','estate-inventory-table']:
 assert item in html,item
for item in ['unique_monitored_products','site-product assignments','Review Apps','estate-product-chips','verified role assignments']:
 assert item in js,item
for item in ['table-layout:fixed','estate-badge--compact','estate-link--subtle','estate-action--unavailable']:
 assert item in css,item
assert 'apps.reason' not in js, 'Full Marketplace limitation must not repeat in site rows'
assert "text('ec-products',s.monitored_product_assignments)" not in js
print('PASS: Estate Configuration compact inventory UI, unique-product metric and single-location Marketplace limitation validated.')
