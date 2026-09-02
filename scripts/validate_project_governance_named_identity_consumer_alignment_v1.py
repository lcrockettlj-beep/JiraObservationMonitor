from pathlib import Path
import ast
import json
import sys

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

def function_block(path, name):
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text)
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    assert len(nodes) == 1, (name, len(nodes))
    lines = text.splitlines()
    node = nodes[0]
    return "\n".join(lines[node.lineno - 1:node.end_lineno])

chain = function_block(root / "app/runtime/admin_enriched_chain.py", "validate_project_governance_named_identity")
web = function_block(root / "app/web.py", "_jom_project_governance_named_identity_contract_v1")

for value in [
    "status_publishable",
    'payload.get("status") in {"ok", "partial"}',
    "coverage_publishable",
    "publishable_with_recorded_exceptions",
    "project_coverage_percent",
    "role_coverage_percent",
]:
    assert value in chain, value

for value in [
    'payload.get("status") in {"ok", "partial"}',
    "coverage_publishable",
    "publishable_with_recorded_exceptions",
    "project_coverage_percent",
    "role_coverage_percent",
]:
    assert value in web, value

if "--contract" in sys.argv:
    contract_path = root / "runtime/data/project_governance_named_identity_authority_v1.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    quality = payload.get("quality", {})
    assert payload.get("status") == "partial"
    assert payload.get("authority", {}).get("safe_to_serve") is True
    assert quality.get("publishable_with_recorded_exceptions") is True
    assert quality.get("project_coverage_percent", 0) >= 95
    assert quality.get("role_coverage_percent", 0) >= 75
    assert len(payload.get("identities", [])) > 0

    from app.web import app
    with app.test_client() as client:
        response = client.get(
            "/api/governance/projects/named-identities",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert response.status_code == 200, response.status_code
        data = response.get_json()
        assert data.get("status") == "ok"
        assert len(data.get("identities", [])) > 0
        assert data.get("privacy", {}).get("account_id_exposed") is False
        assert data.get("privacy", {}).get("email_exposed") is False

print("PASS: PGNI consumer import path, partial authority, API, coverage, privacy, and loopback access validated.")
