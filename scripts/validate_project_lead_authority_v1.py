from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

builder = root / "app/builders/project_lead_authority_v1.py"
assert builder.exists()
text = builder.read_text(encoding="utf-8-sig")
for marker in [
    "jom-project-lead-authority-v1",
    'source_type")=="project_lead"',
    "Project Lead is not Project Owner",
    "account_ids_stored",
]:
    assert marker in text, marker

payload = json.loads(
    (root / "runtime/data/project_lead_authority_v1.json").read_text(
        encoding="utf-8-sig"
    )
)
assert payload["status"] == "partial"
assert payload["summary"]["projects"] == 92
assert payload["summary"]["projects_with_supported_active_lead"] == 69
assert payload["summary"]["projects_without_supported_active_lead_published"] == 23
assert payload["summary"]["lead_coverage_percent"] == 75.0
assert payload["summary"]["distinct_supported_active_leads"] == 20
assert payload["authority"]["safe_to_serve"] is True
assert payload["authority"]["project_owner_semantics_proven"] is False
assert payload["privacy"]["account_ids_stored"] is False
assert payload["privacy"]["email_stored"] is False
assert payload["privacy"]["raw_responses_stored"] is False
assert len(payload["projects"]) == 92

from app.web import app

with app.test_client() as client:
    response = client.get(
        "/api/governance/projects/leads",
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.status_code == 200, response.status_code
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["authority_status"] == "partial"
    assert len(data["projects"]) == 92
    assert data["privacy"]["account_id_exposed"] is False
    assert data["privacy"]["email_exposed"] is False

print(
    "PASS: Project Lead validator import path, partial authority, "
    "92-project reconciliation, API, privacy and Project Owner separation validated."
)
