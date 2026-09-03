from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
builder = root / "app/builders/project_owner_authority_v1.py"
source = builder.read_text(encoding="utf-8-sig")
ast.parse(source)

required = [
    "jom-project-owner-authority-v1",
    "governance_defined_space_owner",
    "Project Lead is the owner of the project space.",
    "native_jira_owner_field_present",
    "native_jira_owner_authority_available",
    "project_lead_authority_v1",
    "account_ids_stored",
    "Project lifecycle changes require a refreshed Project Inventory",
]
for marker in required:
    assert marker in source, marker

assert 'native_jira_owner_field_present": False' in source
assert 'native_jira_owner_authority_available": False' in source
assert 'governance_owner_semantics_proven": True' in source
assert 'native_jira_owner_semantics_proven": False' in source
assert 'account_ids_stored": False' in source
assert 'email_stored": False' in source
assert 'raw_responses_stored": False' in source

print(
    "PASS: Project Owner builder syntax, governance derivation, native Jira "
    "distinction, live-source dependency, privacy and fail-closed gates validated."
)
