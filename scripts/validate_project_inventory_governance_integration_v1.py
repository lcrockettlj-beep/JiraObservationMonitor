from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

html = (root / "templates/governance_projects.html").read_text(encoding="utf-8-sig")
js = (root / "static/js/jom_governance_projects_v1.js").read_text(encoding="utf-8-sig")
css = (root / "static/css/jom_governance_projects_v1.css").read_text(encoding="utf-8-sig")

# Retained Project Inventory capability in the Phase 1 project-centric UX.
for marker in [
    "<!doctype html>",
    '{% include "_nav.html" %}',
    'class="jom-shell gp"',
    "jom_governance_projects_v1.css",
    "jom_governance_projects_v1.js",
    "gp-search",
    "gp-site",
    "gp-governance",
    "gp-governance-rows",
    "gp-rows",
    "Project inventory details",
]:
    assert marker in html, marker

# Phase 1 governance ownership experience replacing the legacy field-filter layout.
for marker in [
    "gp-summary-projects",
    "gp-summary-owned",
    "gp-summary-coverage",
    "gp-summary-gaps",
    "gp-summary-distinct",
    "gp-owner-view",
    "Project Lead is the GLI Space Owner",
    "Jira does not provide a native Project Owner field",
]:
    assert marker in html, marker

for marker in [
    '/api/governance/projects',
    '/api/governance/projects/leads',
    '/api/governance/projects/owners',
    "Project authorities are not synchronized",
    "renderInventory",
    "renderOwners",
    "governance_state",
    "owner_coverage_percent",
]:
    assert marker in js, marker

for marker in [
    "gp__summary",
    "gp__provenance",
    "gp__owner-grid",
    "gp__state--gap",
    "@media(max-width:650px)",
]:
    assert marker in css, marker

# Retired legacy controls are no longer required by the owner contract.
for retired in ["gp-type", "gp-style", "gp-privacy", "gp-simplified", "gp-category"]:
    assert retired not in html, retired

# Frontend privacy boundary.
assert "innerHTML" not in js
assert "account_id" not in js
assert "email" not in js

inventory = json.loads(
    (root / "runtime/data/project_inventory_authority_v1.json").read_text(encoding="utf-8-sig")
)
assert inventory.get("schema") == "jom-project-inventory-authority-v1"
assert inventory.get("status") == "ok"
assert inventory.get("authority", {}).get("safe_to_publish_project_inventory") is True
projects = inventory.get("projects")
assert isinstance(projects, list) and projects
pairs = {
    (
        str(row.get("site_key") or "").strip().lower(),
        str(row.get("project_key") or "").strip().upper(),
    )
    for row in projects
    if isinstance(row, dict)
}
assert len(pairs) == len(projects)
assert all(site and project for site, project in pairs)

from app.web import app

with app.test_client() as client:
    page = client.get("/reports/governance/projects")
    assert page.status_code == 200
    rendered = page.get_data(as_text=True)
    assert "gp-governance-rows" in rendered
    assert "gp-owner-view" in rendered
    assert "Project inventory details" in rendered

    inventory_response = client.get(
        "/api/governance/projects",
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert inventory_response.status_code == 200
    inventory_api = inventory_response.get_json()
    assert inventory_api.get("available") is True
    assert len(inventory_api.get("projects", [])) == len(projects)
    assert inventory_api.get("privacy", {}).get("cloud_ids_exposed") is False
    assert inventory_api.get("privacy", {}).get("tokens_exposed") is False
    assert inventory_api.get("privacy", {}).get("authorization_headers_exposed") is False

    for route in [
        "/api/governance/projects/leads",
        "/api/governance/projects/owners",
    ]:
        response = client.get(route, environ_base={"REMOTE_ADDR": "127.0.0.1"})
        assert response.status_code == 200, (route, response.status_code)
        payload = response.get_json()
        assert payload.get("status") == "ok"
        assert len(payload.get("projects", [])) == len(projects)
        assert payload.get("privacy", {}).get("account_id_exposed") is False
        assert payload.get("privacy", {}).get("email_exposed") is False

print(
    "PASS: Project Inventory authority, Phase 1 project-centric governance UX, "
    "retained search and site filtering, expandable inventory, synchronized Lead "
    "and Owner contracts, responsive layout and privacy gates validated."
)
