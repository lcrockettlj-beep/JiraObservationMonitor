from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from jira_client import JiraApiClient

TRACKED_SITES: List[Tuple[str, str]] = [
    ("gli-global-technology", "GLI Global Technology"),
    ("gli-delivery-tm", "GLI Delivery TM"),
    ("gli-it-project", "GLI IT Project"),
]

ADMIN_RUNTIME_CANDIDATES = [
    "latest_run_admin_enriched_pretty.json",
    "latest_run_admin_enriched.json",
]


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalise_url(value: Any) -> str:
    return str(value or "").strip().rstrip("/").lower()


def normalise_text(value: Any) -> str:
    return str(value or "").strip().lower()


def resource_site_key(resource: Dict[str, Any]) -> str:
    url = normalise_url(resource.get("url"))
    if ".atlassian.net" in url:
        host = url.split("//")[-1].split("/")[0]
        return host.replace(".atlassian.net", "")
    name = normalise_text(resource.get("name"))
    return name.replace(" ", "-")


def find_tracked_resources(resources: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    wanted = {key for key, _label in TRACKED_SITES}
    matched: Dict[str, Dict[str, Any]] = {}
    for resource in resources:
        key = resource_site_key(resource)
        if key in wanted:
            matched[key] = resource
    return matched


def field_first(row: Dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def user_identity(row: Dict[str, Any]) -> Dict[str, Any]:
    active = bool(row.get("active", True))
    return {
        "id": field_first(row, "accountId", "account_id", "id", "Atlassian ID", "User id"),
        "name": field_first(row, "displayName", "name", "publicName", "Name", "User name") or "Unknown user",
        "email": field_first(row, "emailAddress", "email", "Email"),
        "status": "active" if active else "inactive",
        "active": active,
        "account_type": field_first(row, "accountType", "account_type"),
    }


def admin_row_identity(row: Dict[str, Any]) -> Dict[str, str]:
    return {
        "id": field_first(row, "id", "accountId", "account_id", "Atlassian ID", "User id"),
        "email": field_first(row, "email", "Email", "emailAddress"),
        "name": field_first(row, "name", "Name", "displayName", "User name"),
    }


def load_admin_human_allowlist(project_root: Path) -> Dict[str, Set[str]]:
    ids: Set[str] = set()
    emails: Set[str] = set()
    names: Set[str] = set()

    for file_name in ADMIN_RUNTIME_CANDIDATES:
        path = project_root / file_name
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        drilldowns = payload.get("drilldowns", {}) if isinstance(payload, dict) else {}
        section = drilldowns.get("admin::human_accounts") or drilldowns.get("admin::managed_accounts") or {}
        rows = section.get("rows", []) if isinstance(section, dict) else []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            ident = admin_row_identity(row)
            if ident.get("id"):
                ids.add(normalise_text(ident["id"]))
            if ident.get("email"):
                emails.add(normalise_text(ident["email"]))
            if ident.get("name"):
                names.add(normalise_text(ident["name"]))
        break

    return {"ids": ids, "emails": emails, "names": names}


def identity_in_allowlist(identity: Dict[str, Any], allowlist: Dict[str, Set[str]]) -> bool:
    uid = normalise_text(identity.get("id"))
    email = normalise_text(identity.get("email"))
    name = normalise_text(identity.get("name"))
    if uid and uid in allowlist.get("ids", set()):
        return True
    if email and email in allowlist.get("emails", set()):
        return True
    if name and name in allowlist.get("names", set()):
        return True
    return False


def jira_users_for_site(client: JiraApiClient, cloud_id: str, site_key: str, site_label: str, max_results: int = 1000) -> Dict[str, Any]:
    users: List[Dict[str, Any]] = []
    errors: List[str] = []
    start_at = 0
    page_size = max(1, min(int(max_results or 1000), 1000))

    while True:
        result = client.request_jira(
            cloud_id,
            "/rest/api/3/users/search",
            params={"startAt": start_at, "maxResults": page_size},
        )
        if not result.get("ok"):
            errors.append(str(result.get("error") or result.get("status_code") or "unknown error"))
            break
        data = result.get("data", [])
        if not isinstance(data, list):
            errors.append("Unexpected response shape from /rest/api/3/users/search")
            break
        for raw_user in data:
            if not isinstance(raw_user, dict):
                continue
            identity = user_identity(raw_user)
            if not identity.get("id"):
                continue
            users.append({**identity, "site_key": site_key, "site_label": site_label})
        if len(data) < page_size:
            break
        start_at += len(data)
        if start_at > 20000:
            errors.append("Safety stop after 20,000 users for one site")
            break
    return {"users": users, "errors": errors}


def build_access_source(project_root: Path, max_results: int = 1000, admin_human_only: bool = True, atlassian_only: bool = True, active_only: bool = True) -> Dict[str, Any]:
    client = JiraApiClient()
    resources = client.list_accessible_resources()
    matched = find_tracked_resources(resources)
    allowlist = load_admin_human_allowlist(project_root) if admin_human_only else {"ids": set(), "emails": set(), "names": set()}

    by_user: Dict[str, Dict[str, Any]] = {}
    site_results: List[Dict[str, Any]] = []
    collection_errors: Dict[str, List[str]] = {}
    filter_counts = {
        "raw_collected": 0,
        "excluded_non_tracked_resource": 0,
        "excluded_non_atlassian": 0,
        "excluded_inactive": 0,
        "excluded_not_in_admin_humans": 0,
        "accepted": 0,
        "admin_human_allowlist_ids": len(allowlist.get("ids", set())),
        "admin_human_allowlist_emails": len(allowlist.get("emails", set())),
        "admin_human_allowlist_names": len(allowlist.get("names", set())),
    }

    tracked_keys = {key for key, _label in TRACKED_SITES}

    for site_key, site_label in TRACKED_SITES:
        resource = matched.get(site_key)
        if not resource:
            collection_errors[site_key] = ["Tracked site was not present in accessible Jira resources."]
            site_results.append({"site_key": site_key, "site_label": site_label, "cloud_id": "", "raw_users_collected": 0, "accepted_users": 0, "status": "missing_resource"})
            continue

        # Hard guard: even if resource discovery includes other sites, only these three site keys are processed.
        if site_key not in tracked_keys:
            filter_counts["excluded_non_tracked_resource"] += 1
            continue

        cloud_id = str(resource.get("id") or resource.get("cloudId") or "")
        if not cloud_id:
            collection_errors[site_key] = ["Accessible resource did not expose a cloud id."]
            site_results.append({"site_key": site_key, "site_label": site_label, "cloud_id": "", "raw_users_collected": 0, "accepted_users": 0, "status": "missing_cloud_id"})
            continue

        payload = jira_users_for_site(client, cloud_id, site_key, site_label, max_results=max_results)
        collected = payload.get("users", [])
        errors = payload.get("errors", [])
        if errors:
            collection_errors[site_key] = errors

        raw_count = len(collected)
        accepted_count = 0
        filter_counts["raw_collected"] += raw_count

        for user in collected:
            if atlassian_only and normalise_text(user.get("account_type")) != "atlassian":
                filter_counts["excluded_non_atlassian"] += 1
                continue
            if active_only and not bool(user.get("active", True)):
                filter_counts["excluded_inactive"] += 1
                continue
            if admin_human_only and not identity_in_allowlist(user, allowlist):
                filter_counts["excluded_not_in_admin_humans"] += 1
                continue

            uid = str(user.get("id") or "")
            if not uid:
                continue
            if uid not in by_user:
                by_user[uid] = {
                    "id": uid,
                    "name": user.get("name", "Unknown user"),
                    "email": user.get("email", ""),
                    "status": user.get("status", ""),
                    "account_type": user.get("account_type", ""),
                    "sites": {},
                }
            if not by_user[uid].get("email") and user.get("email"):
                by_user[uid]["email"] = user.get("email")
            if by_user[uid].get("name") == "Unknown user" and user.get("name"):
                by_user[uid]["name"] = user.get("name")
            by_user[uid]["sites"][site_key] = site_label
            accepted_count += 1
            filter_counts["accepted"] += 1

        site_results.append({
            "site_key": site_key,
            "site_label": site_label,
            "cloud_id": cloud_id,
            "resource_url": resource.get("url", ""),
            "raw_users_collected": raw_count,
            "accepted_users": accepted_count,
            "status": "ok" if not errors else "partial_error",
        })

    rows: List[Dict[str, Any]] = []
    for user in by_user.values():
        sites = sorted(user.get("sites", {}).values())
        site_count = len(sites)
        if site_count <= 0:
            continue
        category = "high" if site_count >= 3 else "medium" if site_count == 2 else "low"
        rows.append({
            "id": user.get("id", ""),
            "name": user.get("name", "Unknown user"),
            "email": user.get("email", ""),
            "status": user.get("status", ""),
            "account_type": user.get("account_type", ""),
            "site_count": site_count,
            "sites": sites,
            "category": category,
        })

    rows.sort(key=lambda item: (-item["site_count"], str(item.get("name", "")).lower(), str(item.get("email", "")).lower()))
    total_users = len(rows)
    total_assignments = sum(int(item.get("site_count", 0)) for item in rows)

    return {
        "source": "Jira Cloud API filtered through admin human identity allowlist",
        "generated_at_utc": iso_now(),
        "schema": "jom-api-user-access-source-v2-filtered",
        "tracked_sites_only": [key for key, _label in TRACKED_SITES],
        "filters": {
            "admin_human_only": admin_human_only,
            "atlassian_only": atlassian_only,
            "active_only": active_only,
            "reason": "Restricts broad Jira user-search results to the three tracked sites and to known admin-enriched human users where available.",
        },
        "filter_counts": filter_counts,
        "summary": {
            "users_analyzed": total_users,
            "total_site_assignments": total_assignments,
            "average_sites_per_user": round(total_assignments / total_users, 2) if total_users else 0,
            "high_duplication_users": len([row for row in rows if row.get("category") == "high"]),
            "medium_duplication_users": len([row for row in rows if row.get("category") == "medium"]),
            "low_duplication_users": len([row for row in rows if row.get("category") == "low"]),
        },
        "site_results": site_results,
        "collection_errors": collection_errors,
        "users": rows,
        "notes": [
            "Only the three tracked Jira sites are processed, even when OAuth can see more Jira resources.",
            "App accounts are excluded by default.",
            "Users are cross-checked against admin::human_accounts or admin::managed_accounts where available.",
            "CSV import remains available as fallback.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build filtered user access source from Jira Cloud API site user search.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default="static/data/user_access_source.json")
    parser.add_argument("--max-results", type=int, default=1000)
    parser.add_argument("--include-apps", action="store_true", help="Do not exclude accountType != atlassian")
    parser.add_argument("--include-inactive", action="store_true", help="Do not exclude inactive Jira users")
    parser.add_argument("--no-admin-human-filter", action="store_true", help="Do not cross-check against admin::human_accounts")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    payload = build_access_source(
        project_root=project_root,
        max_results=args.max_results,
        admin_human_only=not args.no_admin_human_filter,
        atlassian_only=not args.include_apps,
        active_only=not args.include_inactive,
    )
    output = Path(args.output)
    if not output.is_absolute():
        output = project_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(payload.get("summary", {}), indent=2))
    print("Filter counts:")
    print(json.dumps(payload.get("filter_counts", {}), indent=2))
    if payload.get("collection_errors"):
        print("Collection warnings/errors:")
        print(json.dumps(payload.get("collection_errors"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
