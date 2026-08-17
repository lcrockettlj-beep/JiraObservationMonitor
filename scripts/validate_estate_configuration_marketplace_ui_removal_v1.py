from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]

web = (root / "app/web.py").read_text(encoding="utf-8")
html = (
    root / "templates/admin_estate_configuration.html"
).read_text(encoding="utf-8")
js = (
    root / "static/js/jom_admin_estate_configuration_v1.js"
).read_text(encoding="utf-8")

ast.parse(web)

start = web.index(
    "# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 START ---"
)
end = web.index(
    "# --- JOM_ADMIN_ESTATE_CONFIGURATION_AUTHORITY_V3 END ---",
    start,
)
owner = web[start:end]

for text, label in [
    (owner, "web owner"),
    (html, "HTML"),
    (js, "JavaScript"),
]:
    for forbidden in [
        "Marketplace Apps",
        "marketplace_apps",
        "marketplace_app_count",
        "ec-apps",
        "ec-rail-apps",
        "Review Apps",
        "estate_marketplace_app_authority_v1.json",
    ]:
        assert forbidden not in text, (label, forbidden)

for required in [
    "Monitored Sites",
    "Monitored Products",
    "Ownership Coverage",
    "Products and ownership",
    'colspan="4"',
]:
    assert required in html, required

for required in [
    "monitored_products",
    "assignment_count",
    "blocking_action_items",
    "No configuration actions",
]:
    assert required in js, required

print(
    "PASS: Estate Configuration Marketplace presentation removed; "
    "historical limitation authority retained outside the page."
)
