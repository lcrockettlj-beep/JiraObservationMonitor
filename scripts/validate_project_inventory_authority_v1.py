from pathlib import Path
import ast
import json
import sys

root = Path(__file__).resolve().parents[1]
owner = root / "app/builders/project_inventory_authority_v1.py"
text = owner.read_text(encoding="utf-8-sig")
ast.parse(text)

for value in [
    "rest/api/3/project/search",
    "pagination_complete_all_sites",
    "historical_expected_count_used",
    "project_owners",
    "archived_projects",
    "inactive_projects",
    "project_permissions",
    "project_governance",
    "fabricated_projects",
    "raw_responses_stored",
]:
    assert value in text, value

assert "leadAccountId" not in text

output = root / "runtime/data/project_inventory_authority_v1.json"

if "--contract" in sys.argv:
    assert output.exists(), "contract missing"
    payload = json.loads(output.read_text(encoding="utf-8-sig"))
    summary = payload.get("summary") or {}
    authority = payload.get("authority") or {}
    capabilities = payload.get("capabilities") or {}
    projects = payload.get("projects") or []
    sites = payload.get("sites") or []

    assert payload.get("schema") == "jom-project-inventory-authority-v1"
    assert payload.get("status") == "ok"
    assert authority.get("safe_to_publish_project_inventory") is True
    assert authority.get("pagination_complete_all_sites") is True
    assert summary.get("monitored_site_count") == summary.get("successful_site_count")
    assert summary.get("failed_site_count") == 0
    assert summary.get("visible_project_count") == len(projects)
    assert summary.get("collected_project_rows") == len(projects)
    assert summary.get("duplicate_site_project_key_count") == 0
    assert len(sites) == summary.get("monitored_site_count")
    assert all(site.get("status") == "ok" for site in sites)
    assert all(site.get("pagination_complete") is True for site in sites)
    assert capabilities.get("project_inventory", {}).get("available") is True

    unavailable = (
        "project_leads",
        "project_owners",
        "archived_projects",
        "inactive_projects",
        "project_permissions",
        "project_governance",
    )

    for key in unavailable:
        capability = capabilities.get(key) or {}
        assert capability.get("available") is False, key
        assert str(capability.get("reason") or "").strip(), key

print(
    "PASS: Project Inventory Authority v1 owner, live contract, pagination, "
    "population and unavailable capability gates validated."
)
