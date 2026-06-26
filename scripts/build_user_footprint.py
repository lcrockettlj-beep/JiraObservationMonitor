import json
from pathlib import Path
from typing import Any, Dict, List

TRACKED_SITES = [("gli-global-technology", "GLI Global Technology"), ("gli-delivery-tm", "GLI Delivery TM"), ("gli-it-project", "GLI IT Project")]
RUNTIME_CANDIDATES = ["latest_run_admin_enriched_pretty.json", "latest_run_admin_enriched.json", "latest_run_pretty.json", "latest_run.json"]

def load_runtime(project_root: Path) -> Dict[str, Any]:
    for name in RUNTIME_CANDIDATES:
        path = project_root / name
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data["__source_file"] = name
                    return data
            except Exception:
                pass
    return {"__source_file": "none"}

def user_id(row: Dict[str, Any]) -> str:
    return str(row.get("id") or row.get("accountId") or row.get("User id") or row.get("Atlassian ID") or row.get("email") or row.get("Email") or "").strip()

def user_name(row: Dict[str, Any]) -> str:
    return str(row.get("name") or row.get("displayName") or row.get("User name") or row.get("Name") or row.get("email") or row.get("Email") or "Unknown user").strip()

def user_email(row: Dict[str, Any]) -> str:
    return str(row.get("email") or row.get("Email") or row.get("emailAddress") or "").strip()

def add_user(users: Dict[str, Dict[str, Any]], row: Dict[str, Any], site_key: str, site_label: str) -> None:
    uid = user_id(row)
    if not uid:
        return
    if uid not in users:
        users[uid] = {"id": uid, "name": user_name(row), "email": user_email(row), "sites": {}}
    users[uid]["sites"][site_key] = site_label

def collect_from_drilldowns(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    users = {}
    drilldowns = payload.get("drilldowns", {}) if isinstance(payload.get("drilldowns"), dict) else {}
    for site_key, site_label in TRACKED_SITES:
        for key in (f"site::{site_key}", f"access::Jira - {site_key}", f"access::Jira Software - {site_key}"):
            section = drilldowns.get(key) or {}
            rows = section.get("rows", []) if isinstance(section, dict) else []
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        add_user(users, row, site_key, site_label)
    return users

def collect_from_users_export(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    users = {}
    candidates = [payload.get("users_rows"), payload.get("users_export_rows"), payload.get("users_export"), payload.get("users")]
    for rows in candidates:
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    for site_key, site_label in TRACKED_SITES:
                        if str(row.get(f"Jira - {site_key}", "")).strip().lower() == "user":
                            add_user(users, row, site_key, site_label)
    return users

def merge_users(*sources):
    merged = {}
    for source in sources:
        for uid, row in source.items():
            if uid not in merged:
                merged[uid] = row
            else:
                merged[uid]["sites"].update(row.get("sites", {}))
    return merged

def build_payload(project_root: Path):
    runtime = load_runtime(project_root)
    users = merge_users(collect_from_drilldowns(runtime), collect_from_users_export(runtime))
    rows = []
    for user in users.values():
        site_labels = sorted(user.get("sites", {}).values())
        site_count = len(site_labels)
        category = "high" if site_count >= 3 else "medium" if site_count == 2 else "low"
        rows.append({"id": user.get("id", ""), "name": user.get("name", "Unknown user"), "email": user.get("email", ""), "site_count": site_count, "sites": site_labels, "category": category})
    rows.sort(key=lambda item: (-item["site_count"], item["name"].lower(), item.get("email", "").lower()))
    total_users = len(rows)
    total_site_assignments = sum(item["site_count"] for item in rows)
    return {"source": runtime.get("__source_file", "none"), "summary": {"users_analyzed": total_users, "total_site_assignments": total_site_assignments, "average_sites_per_user": round(total_site_assignments / total_users, 2) if total_users else 0, "high_duplication_users": len([x for x in rows if x["category"] == "high"]), "medium_duplication_users": len([x for x in rows if x["category"] == "medium"]), "low_duplication_users": len([x for x in rows if x["category"] == "low"])}, "users": rows}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = build_payload(Path(args.project_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload.get("summary", {}), indent=2))
if __name__ == "__main__":
    main()
