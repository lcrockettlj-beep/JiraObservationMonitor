from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Any, Dict, List

TRACKED_SITES = [
    ("gli-global-technology", "GLI Global Technology"),
    ("gli-delivery-tm", "GLI Delivery TM"),
    ("gli-it-project", "GLI IT Project"),
]
TRUE_VALUES = {"user", "yes", "true", "1", "active", "enabled", "licensed", "y"}

def clean(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").strip()

def norm(value: Any) -> str:
    return clean(value).lower()

def has_access(value: Any) -> bool:
    return norm(value) in TRUE_VALUES

def row_get(row: Dict[str, Any], key: str) -> str:
    target = norm(key)
    for existing_key, value in row.items():
        if norm(existing_key) == target:
            return clean(value)
    return ""

def first_value(row: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = row_get(row, key)
        if value:
            return value
    return ""

def import_csv(source: Path) -> Dict[str, Any]:
    users: Dict[str, Dict[str, Any]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [clean(name) for name in (reader.fieldnames or [])]
        for raw_row in reader:
            row = {clean(k): clean(v) for k, v in raw_row.items() if k is not None}
            email = first_value(row, ["email", "Email", "Email address", "emailAddress"])
            name = first_value(row, ["name", "Name", "User name", "displayName", "Display name"]) or email or "Unknown user"
            uid = first_value(row, ["id", "User id", "Atlassian ID", "accountId", "accountID"]) or email or name
            if not uid:
                continue
            if uid not in users:
                users[uid] = {"id": uid, "name": name, "email": email, "status": first_value(row, ["status", "Status", "User status"]), "sites": {}}
            for site_key, site_label in TRACKED_SITES:
                preferred = f"Jira - {site_key}"
                value = row_get(row, preferred)
                if not value:
                    for field in fieldnames:
                        if site_key in norm(field) and "jira" in norm(field):
                            value = row_get(row, field)
                            break
                if has_access(value):
                    users[uid]["sites"][site_key] = site_label

    rows: List[Dict[str, Any]] = []
    for user in users.values():
        sites = sorted(user.get("sites", {}).values())
        site_count = len(sites)
        if site_count <= 0:
            continue
        category = "high" if site_count >= 3 else "medium" if site_count == 2 else "low"
        rows.append({"id": user["id"], "name": user["name"], "email": user["email"], "status": user.get("status", ""), "site_count": site_count, "sites": sites, "category": category})
    rows.sort(key=lambda item: (-item["site_count"], item["name"].lower(), item.get("email", "").lower()))
    total_users = len(rows)
    total_assignments = sum(item["site_count"] for item in rows)
    return {
        "source": str(source),
        "schema": "jom-user-access-source-v1",
        "summary": {
            "users_analyzed": total_users,
            "total_site_assignments": total_assignments,
            "average_sites_per_user": round(total_assignments / total_users, 2) if total_users else 0,
            "high_duplication_users": len([x for x in rows if x["category"] == "high"]),
            "medium_duplication_users": len([x for x in rows if x["category"] == "medium"]),
            "low_duplication_users": len([x for x in rows if x["category"] == "low"]),
        },
        "users": rows,
        "notes": [
            "Imported from user access CSV source.",
            "Headers and cell values are trimmed before processing.",
            "True access values: User, Yes, True, 1, Active, Enabled, Licensed, Y."
        ],
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Import user access CSV into JOM JSON format.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.source)
    output = Path(args.output)
    if not source.exists():
        raise SystemExit(f"Source CSV not found: {source}")
    payload = import_csv(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
