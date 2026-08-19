from pathlib import Path
import ast, json, sys
root=Path(__file__).resolve().parents[1]
owners={"chain":root/"app/runtime/admin_enriched_chain.py","web":root/"app/web.py","template":root/"templates/governance_projects.html","nav":root/"templates/_nav.html","js":root/"static/js/jom_governance_projects_v1.js","css":root/"static/css/jom_governance_projects_v1.css","collector":root/"app/builders/project_inventory_authority_v1.py","shell_css":root/"static/css/jom_atlassian_command.css"}
for name,path in owners.items(): assert path.exists(),f"missing {name}: {path}"
ast.parse(owners["chain"].read_text(encoding="utf-8-sig")); ast.parse(owners["web"].read_text(encoding="utf-8-sig"))
chain=owners["chain"].read_text(encoding="utf-8-sig"); web=owners["web"].read_text(encoding="utf-8-sig"); html=owners["template"].read_text(encoding="utf-8-sig"); js=owners["js"].read_text(encoding="utf-8-sig"); shell_css=owners["shell_css"].read_text(encoding="utf-8-sig")
assert '{% extends "base.html" %}' not in html and "base.html" not in html
for value in ["<!doctype html>","{% include \"_nav.html\" %}","class=\"jom-shell gp\"","jom_governance_projects_v1.css","jom_governance_projects_v1.js","gp-site","gp-type","gp-style","gp-privacy","gp-simplified","gp-category","gp-search"]: assert value in html,value
assert ".jom-shell" in shell_css,"Shared JOM shell layout contract missing from jom_atlassian_command.css"
for value in ["app.builders.project_inventory_authority_v1","validate_project_inventory","project_inventory_authority_v1.json","no_duplicate_site_project_keys","project_count_reconciled"]: assert value in chain,value
for value in ["/api/governance/projects","jom-project-inventory-governance-api-v1","cloud_ids_exposed","counts_reconcile","pagination_complete"]: assert value in web,value
assert "governance_report" not in js.lower()
assert "cloud_id" not in js and "authorization" not in js.lower() and "token" not in js.lower()
sys.path.insert(0,str(root))
from app.web import app
with app.test_client() as client:
 response=client.get("/reports/governance/projects")
 assert response.status_code==200,f"Governance Projects render failed: HTTP {response.status_code}"
 body=response.get_data(as_text=True)
 assert 'class="jom-shell gp"' in body and 'id="governance-projects"' in body
 assert 'jom_governance_projects_v1.js' in body and 'jom_governance_projects_v1.css' in body
contract=root/"runtime/data/project_inventory_authority_v1.json"
if "--contract" in sys.argv:
 assert contract.exists(),"Project Inventory contract missing"
 p=json.loads(contract.read_text(encoding="utf-8-sig")); s=p.get("summary",{}); a=p.get("authority",{}); projects=p.get("projects",[]); sites=p.get("sites",[])
 pairs={(str(x.get("site_key") or "").lower(),str(x.get("project_key") or "").upper()) for x in projects}
 assert p.get("status")=="ok" and a.get("safe_to_publish_project_inventory") is True
 assert a.get("pagination_complete_all_sites") is True and all(x.get("status")=="ok" and x.get("pagination_complete") is True for x in sites)
 assert s.get("monitored_site_count")==s.get("successful_site_count")==len(sites)
 assert s.get("visible_project_count")==s.get("collected_project_rows")==len(projects)
 assert s.get("duplicate_site_project_key_count")==0 and len(pairs)==len(projects)
print("PASS: Project Inventory Governance Phase 2 contract, Flask render, and shared navigation-offset shell validated.")
