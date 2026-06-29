import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMED_ACCESS = ROOT / "static" / "data" / "admin_named_access.json"
GROUP_EXPANSION = ROOT / "static" / "data" / "admin_group_expansion.json"
SITE_REGISTRY = ROOT / "static" / "data" / "site_registry.json"
OUT = ROOT / "static" / "data" / "named_access_truth_v2.json"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def monitored_keys():
    registry = read_json(SITE_REGISTRY, {}) or {}
    keys = set()
    for site in registry.get("sites", []):
        classification = str(site.get("classification") or "").lower()
        if classification == "monitored":
            for field in ("site_key", "site_name", "cloud_id", "url", "site_url"):
                value = site.get(field)
                if value:
                    keys.add(str(value))
    return keys


def add_access(users, account_id, site_key, source, product="jira-software"):
    if not account_id or not site_key:
        return
    user = users.setdefault(account_id, {
        "account_id": account_id,
        "sites": {},
        "access_sources": set(),
    })
    site = user["sites"].setdefault(site_key, {
        "site_key": site_key,
        "products": set(),
        "sources": set(),
    })
    site["products"].add(product)
    site["sources"].add(source)
    user["access_sources"].add(source)


def main():
    named = read_json(NAMED_ACCESS)
    group = read_json(GROUP_EXPANSION)
    monitored = monitored_keys()
    users = {}
    warnings = []

    if not named:
        warnings.append("admin_named_access.json is missing or unreadable.")
    else:
        for row in named.get("users", []):
            account_id = row.get("account_id") or row.get("accountId")
            for access in row.get("jira_access", []) or []:
                site_key = access.get("site_key") or access.get("site_name") or access.get("cloud_id")
                if monitored and site_key not in monitored:
                    continue
                add_access(users, account_id, site_key, "direct", access.get("resource_owner") or "jira-software")

    group_safe = bool(group and group.get("safe_to_use_for_named_access") is True and group.get("source_status") == "generated")
    if group_safe:
        for group_row in group.get("groups", []):
            product = group_row.get("product") or "jira-software"
            sites = group_row.get("sites") or []
            members = group_row.get("members") or []
            for member in members:
                account_id = member.get("account_id") if isinstance(member, dict) else member
                for site_key in sites:
                    if monitored and site_key not in monitored:
                        continue
                    add_access(users, account_id, site_key, "group", product)
    else:
        warnings.append("Group-derived access expansion is unavailable or not safe_to_use_for_named_access. Named access truth v2 remains incomplete.")

    user_rows = []
    total_assignments = 0
    for account_id, user in users.items():
        site_rows = []
        for site_key, site in sorted(user["sites"].items()):
            products = sorted(site["products"])
            sources = sorted(site["sources"])
            total_assignments += len(products)
            site_rows.append({
                "site_key": site_key,
                "products": products,
                "sources": sources,
            })
        user_rows.append({
            "account_id": account_id,
            "site_count": len(site_rows),
            "sites": site_rows,
            "access_sources": sorted(user["access_sources"]),
        })

    payload = {
        "schema": "jom-named-access-truth-v2",
        "generated_at_utc": now_utc(),
        "source_status": "incomplete" if warnings else "generated",
        "safe_to_enable_named_access_ui": False,
        "reason": "Named access truth v2 is not safe until direct + group-derived assignments reconcile to billing/API product counts.",
        "sources": {
            "direct_named_access": str(NAMED_ACCESS.relative_to(ROOT)),
            "group_expansion": str(GROUP_EXPANSION.relative_to(ROOT)),
            "site_registry": str(SITE_REGISTRY.relative_to(ROOT)),
        },
        "summary": {
            "unique_users": len(user_rows),
            "total_product_access_assignments": total_assignments,
            "group_expansion_safe": group_safe,
            "warning_count": len(warnings),
        },
        "warnings": warnings,
        "users": sorted(user_rows, key=lambda item: (-item["site_count"], item["account_id"] or "")),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"source_status": payload["source_status"], "safe": payload["safe_to_enable_named_access_ui"], "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
