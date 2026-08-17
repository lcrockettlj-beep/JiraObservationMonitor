from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]/"JOM Living Guide"
files=["BOOKSYNC Guide.md","GitHub Repository Record.json","JOM Change History.md","JOM Progress and Improvements.md","JOM Quick Start.md","JOM Recovery Guide.md","JOM System and File Map.md","The Jira Observation Monitor Guide.md"]
for name in files: assert (root/name).exists(), name
combined="\n".join((root/n).read_text(encoding="utf-8") for n in files if n.endswith(".md"))
for item in ["jom-admin-estate-configuration-authority-v3","33 role-assignment","6 proven site-product assignments","HTTP 406","HTTP 401","safe_to_publish_marketplace_apps","/site-workspace/<site-key>","Discovery remains parked"]: assert item in combined,item
data=json.loads((root/"GitHub Repository Record.json").read_text(encoding="utf-8")); b=data["booksync"]
assert b["ownership_assignments"]==33 and b["blocking_actions"]==0
assert b["milestone_status"]=="completed_and_accepted_pending_commit_and_push"
print("PASS: Estate Configuration v3 BOOKSYNC owners, continuity, authority boundaries and pending-commit state validated.")
