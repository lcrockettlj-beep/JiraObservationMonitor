from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
web = (root / "app/web.py").read_text(encoding="utf-8")
html = (root / "templates/admin_estate_configuration.html").read_text(encoding="utf-8")
js = (root / "static/js/jom_admin_estate_configuration_v1.js").read_text(encoding="utf-8")
css = (root / "static/css/jom_admin_estate_configuration_v1.css").read_text(encoding="utf-8")

ast.parse(web)
start = web.index("# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 START ---")
end = web.index("# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 END ---", start)
owner = web[start:end]

for text, label in [(owner, "web owner"), (html, "HTML"), (js, "JavaScript")]:
    for forbidden in ["Marketplace Apps", "marketplace_apps", "marketplace_app_count", "ec-apps", "ec-rail-apps", "Review Apps", "estate_marketplace_app_authority_v1.json"]:
        assert forbidden not in text, (label, forbidden)

assert 'id="ec-products"' not in html
assert 'id="ec-products-note"' not in html
assert "text('ec-products'" not in js
assert "text('ec-products-note'" not in js

for required in ["Monitored Sites", "Ownership Coverage", "Products and ownership", "<th>Monitored Products</th>", 'colspan="4"']:
    assert required in html, required

for required in ["monitored_products", "estate-product-chips", "assignment_count", "blocking_action_items", "No configuration actions", "sourceName", "estate-source-file", "title=\"'+esc(full)+'\""]:
    assert required in js, required

assert "runtime_file" in js
assert "split('/')" in js
assert "replace(/\\\\/g,'/')" in js
assert ".estate-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in css
for required in [".estate-source-file", "overflow-wrap:anywhere", "word-break:break-word", "min-width:0"]:
    assert required in css, required

for required in ["unique_monitored_products", "monitored_product_assignments", "monitored_products", "product_coverage_percent"]:
    assert required in owner, required

print("PASS: Estate Configuration two-metric layout and source-filename presentation validated; product detail authority retained.")
