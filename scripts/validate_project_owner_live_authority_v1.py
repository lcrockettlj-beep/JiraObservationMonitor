from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))


def load(relative):
    path = root / relative
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict), relative
    return payload


def rows(payload):
    value = payload.get("projects")
    assert isinstance(value, list)
    assert all(isinstance(row, dict) for row in value)
    return value


def key(row):
    return (
        str(row.get("site_key") or "").strip().lower(),
        str(row.get("project_key") or "").strip().upper(),
    )

inventory = load("runtime/data/project_inventory_authority_v1.json")
lead = load("runtime/data/project_lead_authority_v1.json")
owner = load("runtime/data/project_owner_authority_v1.json")

assert inventory.get("schema") == "jom-project-inventory-authority-v1"
assert inventory.get("status") == "ok"
assert inventory.get("authority", {}).get("safe_to_publish_project_inventory") is True
assert lead.get("schema") == "jom-project-lead-authority-v1"
assert lead.get("status") in {"ok", "partial"}
assert lead.get("authority", {}).get("safe_to_serve") is True
assert owner.get("schema") == "jom-project-owner-authority-v1"
assert owner.get("status") in {"ok", "partial"}
assert owner.get("authority", {}).get("safe_to_serve") is True

inventory_rows = rows(inventory)
lead_rows = rows(lead)
owner_rows = rows(owner)
inventory_keys = {key(row) for row in inventory_rows}
lead_keys = {key(row) for row in lead_rows}
owner_keys = {key(row) for row in owner_rows}
assert all(site and project for site, project in inventory_keys)
assert len(inventory_keys) == len(inventory_rows)
assert len(lead_keys) == len(lead_rows)
assert len(owner_keys) == len(owner_rows)
assert lead_keys == owner_keys
assert lead_keys <= inventory_keys

lead_by_key = {key(row): row for row in lead_rows}
projects_with_owner = 0
distinct_owners = set()
for owner_row in owner_rows:
    matching_lead = lead_by_key[key(owner_row)]
    lead_names = {
        str(item.get("display_name") or "").strip()
        for item in matching_lead.get("leads", [])
        if isinstance(item, dict) and str(item.get("display_name") or "").strip()
    }
    owner_items = owner_row.get("owners")
    assert isinstance(owner_items, list)
    owner_names = {
        str(item.get("display_name") or "").strip()
        for item in owner_items
        if isinstance(item, dict) and str(item.get("display_name") or "").strip()
    }
    assert owner_names == lead_names
    assert all(
        item.get("owner_source") == "project_lead_authority_v1"
        and item.get("owner_type") == "governance_defined_space_owner"
        for item in owner_items
        if isinstance(item, dict)
    )
    assert owner_row.get("supported_owner_count") == len(owner_items)
    projects_with_owner += int(bool(owner_items))
    distinct_owners.update(owner_names)

total = len(owner_rows)
gaps = total - projects_with_owner
coverage = round(projects_with_owner * 100.0 / total, 1) if total else 0.0
summary = owner.get("summary", {})
assert summary.get("projects") == total == len(lead_rows)
assert summary.get("projects_with_governance_defined_owner") == projects_with_owner
assert summary.get("projects_without_governance_defined_owner_published") == gaps
assert summary.get("owner_coverage_percent") == coverage
assert summary.get("distinct_governance_defined_owners") == len(distinct_owners)

assert owner.get("definition", {}).get("owner_source") == "project_lead_authority_v1"
assert owner.get("definition", {}).get("owner_type") == "governance_defined_space_owner"
assert owner.get("definition", {}).get("native_jira_owner_field_present") is False
assert owner.get("authority", {}).get("governance_owner_semantics_proven") is True
assert owner.get("authority", {}).get("native_jira_owner_semantics_proven") is False
assert owner.get("privacy", {}).get("account_ids_stored") is False
assert owner.get("privacy", {}).get("email_stored") is False
assert owner.get("privacy", {}).get("raw_responses_stored") is False

chain = (root / "app/runtime/admin_enriched_chain.py").read_text(encoding="utf-8-sig")
refresh = (root / "app/runtime/runtime_sources_refresh.py").read_text(encoding="utf-8-sig")
assert "project_owner_authority" in chain
assert "project_lead_authority" in chain
assert chain.index('"project_lead_authority"') < chain.index('"project_owner_authority"')
assert "project_owner_authority_v1.json" in refresh

from app.web import app
with app.test_client() as client:
    response = client.get(
        "/api/governance/projects/owners",
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.status_code == 200
    api = response.get_json()
    assert api.get("status") == "ok"
    assert api.get("authority_status") == owner.get("status")
    assert api.get("summary") == summary
    assert len(api.get("projects", [])) == total
    assert api.get("privacy", {}).get("account_id_exposed") is False
    assert api.get("privacy", {}).get("email_exposed") is False
    assert api.get("definition", {}).get("native_jira_owner_field_present") is False
    denied = client.get(
        "/api/governance/projects/owners",
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )
    assert denied.status_code == 403

print(
    "PASS: Live Project Inventory, Project Lead and Project Owner contracts "
    "dynamically reconcile; governance derivation, counts, API, privacy, "
    "dependency order and native Jira separation validated."
)
