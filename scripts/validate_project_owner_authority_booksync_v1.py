from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
guide = root / "JOM Living Guide"
markdown = [
    "BOOKSYNC Guide.md",
    "JOM Change History.md",
    "JOM Progress and Improvements.md",
    "JOM Quick Start.md",
    "JOM Recovery Guide.md",
    "JOM System and File Map.md",
    "The Jira Observation Monitor Guide.md",
]
common_markers = [
    "Project Owner Live Authority Correction v1",
    "Projects reconciled: 76",
    "Projects with governance-defined owner: 73",
    "Owner coverage: 96.1%",
    "Distinct governance-defined owners: 21",
    "must not be hard-coded",
    "Governance Projects UX Phase 1",
]
dependency_markers = [
    "The required authority order remains:",
    "1. Project Inventory refreshes from current Jira project authority.",
    "2. Project Lead refreshes against the current Project Inventory",
    "3. Project Owner derives from the current Project Lead authority",
]
for filename in markdown:
    text = (guide / filename).read_text(encoding="utf-8-sig")
    for marker in common_markers:
        assert marker in text, (filename, marker)
    positions = [text.find(marker) for marker in dependency_markers]
    assert all(position >= 0 for position in positions), (filename, dependency_markers, positions)
    assert positions == sorted(positions), (filename, "dependency order", positions)

record = json.loads(
    (guide / "GitHub Repository Record.json").read_text(encoding="utf-8-sig")
)["project_owner_live_authority_correction_v1"]
assert record["current_projects"] == 76
assert record["current_projects_with_governance_defined_owner"] == 73
assert record["current_projects_without_governance_defined_owner_published"] == 3
assert record["current_owner_coverage_percent"] == 96.1
assert record["current_distinct_governance_defined_owners"] == 21
assert record["native_jira_owner_field_present"] is False
assert record["historical_fixed_counts_prohibited"] is True
assert record["live_dependency_order"] == [
    "project_inventory_authority_v1",
    "project_lead_authority_v1",
    "project_owner_authority_v1",
]
print(
    "PASS: Project Owner live correction, current evidence, semantic dependency "
    "order, recovery and next workstream validated across eight owners."
)
