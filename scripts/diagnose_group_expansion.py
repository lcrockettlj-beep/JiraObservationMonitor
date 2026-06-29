import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "group_expansion_diagnostics_v1_1.json"
SUMMARY_MD = ROOT / "reports" / "group_expansion_diagnostics_v1_1.md"
SITE_REGISTRY = ROOT / "static" / "data" / "site_registry.json"
API_BASE = "https://api.atlassian.com"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def request_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def page_get(url, token, max_pages=2):
    rows = []
    next_url = url
    pages = 0
    while next_url and pages < max_pages:
        pages += 1
        payload = request_json(next_url, token)
        data = payload.get("data")
        if isinstance(data, list):
            rows.extend(data)
        elif isinstance(payload.get("values"), list):
            rows.extend(payload.get("values"))
        links = payload.get("links") or {}
        nxt = links.get("next") if isinstance(links, dict) else None
        if isinstance(nxt, dict):
            next_url = nxt.get("href")
        elif isinstance(nxt, str) and nxt.startswith("http"):
            next_url = nxt
        elif isinstance(nxt, str) and nxt.startswith("/"):
            next_url = API_BASE + nxt
        else:
            next_url = None
        time.sleep(0.05)
    return rows


def monitored_resource_map():
    registry = read_json(SITE_REGISTRY, {}) or {}
    mappings = {}
    monitored = []
    for site in registry.get("sites", []):
        if str(site.get("classification") or "").lower() != "monitored":
            continue
        site_key = site.get("site_key") or site.get("site_name") or site.get("name") or site.get("url") or site.get("site_url")
        monitored.append({"site_key": site_key, "cloud_id": site.get("cloud_id"), "url": site.get("url") or site.get("site_url")})
        for field in ("cloud_id", "resource_id", "id", "site_id", "url", "site_url", "site_key", "site_name", "name"):
            if site.get(field) and site_key:
                mappings[str(site.get(field))] = str(site_key)
    return mappings, monitored


def extract_group_id(group):
    return str(group.get("id") or group.get("groupId") or group.get("uuid") or "")


def extract_group_name(group):
    return str(group.get("name") or group.get("displayName") or group.get("groupName") or extract_group_id(group))


def is_probable_jira_group(group):
    text = " ".join(str(group.get(k) or "") for k in ("name", "displayName", "description")).lower()
    hints = ["jira", "software", "jsw", "atlassian-addons", "site-admin", "product"]
    return any(h in text for h in hints)


def extract_role_resource_ids(role):
    ids = []
    for key in ("resourceId", "resource_id", "resourceOwner", "resourceOwnerId", "cloudId", "cloud_id"):
        if role.get(key):
            ids.append(str(role.get(key)))
    for key in ("resource", "site", "context"):
        nested = role.get(key)
        if isinstance(nested, dict):
            for nkey in ("id", "resourceId", "cloudId", "cloud_id", "url", "name"):
                if nested.get(nkey):
                    ids.append(str(nested.get(nkey)))
    return sorted(set(ids))


def collect_members(org_id, directory_id, group_id, token, max_pages):
    endpoints = []
    endpoints.append(("memberships", f"{API_BASE}/admin/v2/orgs/{org_id}/directories/{directory_id}/groups/{group_id}/memberships?limit=100"))
    endpoints.append(("users_groupIds_filter", f"{API_BASE}/admin/v2/orgs/{org_id}/directories/{directory_id}/users?{urllib.parse.urlencode({'limit':100,'groupIds':group_id})}"))
    results = []
    errors = []
    for name, url in endpoints:
        try:
            rows = page_get(url, token, max_pages=max_pages)
            for row in rows:
                if isinstance(row, dict):
                    account_id = row.get("accountId") or row.get("account_id") or row.get("id") or row.get("userId")
                    if account_id:
                        results.append({"account_id": str(account_id), "source": name})
            if results:
                return results, errors
        except Exception as exc:
            errors.append({"endpoint": name, "error": str(exc)})
    return results, errors


def main():
    parser = argparse.ArgumentParser(description="Diagnose Atlassian Admin group expansion collection without enabling named access.")
    parser.add_argument("--org-id", default=os.getenv("ATLASSIAN_ORG_ID") or os.getenv("ATLASSIAN_ADMIN_ORG_ID") or "")
    parser.add_argument("--directory-id", default=os.getenv("ATLASSIAN_DIRECTORY_ID") or "")
    parser.add_argument("--token", default=os.getenv("ATLASSIAN_ADMIN_TOKEN") or os.getenv("ATLASSIAN_ADMIN_API_KEY") or "")
    parser.add_argument("--max-groups", type=int, default=50)
    parser.add_argument("--max-role-groups", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args()

    resource_map, monitored_sites = monitored_resource_map()
    diag = {
        "schema": "jom-group-expansion-diagnostics-v1.1",
        "generated_at_utc": now_utc(),
        "inputs_present": {
            "token": bool(args.token),
            "org_id": bool(args.org_id),
            "directory_id": bool(args.directory_id),
        },
        "monitored_sites": monitored_sites,
        "resource_map_key_count": len(resource_map),
        "groups_seen": 0,
        "probable_jira_groups_seen": 0,
        "role_assignment_rows_seen": 0,
        "role_resource_ids_seen": [],
        "mapped_resource_ids": [],
        "unmapped_resource_ids": [],
        "member_rows_seen": 0,
        "candidate_groups": [],
        "errors": [],
        "conclusion": "not_run",
    }

    if not args.token or not args.org_id or not args.directory_id:
        diag["conclusion"] = "missing_required_inputs"
        write_json(OUT, diag)
        print(json.dumps({"conclusion": diag["conclusion"], "output": str(OUT)}, indent=2))
        return 0

    try:
        groups_url = f"{API_BASE}/admin/v2/orgs/{args.org_id}/directories/{args.directory_id}/groups?limit=100"
        groups = page_get(groups_url, args.token, max_pages=args.max_pages)
    except Exception as exc:
        diag["conclusion"] = "groups_api_failed"
        diag["errors"].append({"stage": "groups", "error": str(exc)})
        write_json(OUT, diag)
        print(json.dumps({"conclusion": diag["conclusion"], "output": str(OUT)}, indent=2))
        return 0

    diag["groups_seen"] = len(groups)
    probable = [g for g in groups if isinstance(g, dict) and is_probable_jira_group(g)]
    diag["probable_jira_groups_seen"] = len(probable)
    groups_to_probe = probable[:args.max_role_groups] if probable else groups[:args.max_groups]

    all_resource_ids = set()
    mapped = set()
    unmapped = set()

    for group in groups_to_probe:
        group_id = extract_group_id(group)
        group_name = extract_group_name(group)
        if not group_id:
            continue
        group_diag = {"group_id": group_id, "group_name": group_name, "role_rows": 0, "resource_ids": [], "mapped_sites": [], "member_rows": 0, "errors": []}
        roles_url = f"{API_BASE}/admin/v2/orgs/{args.org_id}/directories/{args.directory_id}/groups/{group_id}/role-assignments?limit=100"
        try:
            roles = page_get(roles_url, args.token, max_pages=args.max_pages)
        except Exception as exc:
            group_diag["errors"].append({"stage": "role_assignments", "error": str(exc)})
            diag["errors"].append({"group_id": group_id, "group_name": group_name, "stage": "role_assignments", "error": str(exc)})
            roles = []
        group_diag["role_rows"] = len(roles)
        diag["role_assignment_rows_seen"] += len(roles)
        for role in roles:
            if not isinstance(role, dict):
                continue
            for rid in extract_role_resource_ids(role):
                all_resource_ids.add(rid)
                group_diag["resource_ids"].append(rid)
                if rid in resource_map:
                    mapped.add(rid)
                    group_diag["mapped_sites"].append(resource_map[rid])
                else:
                    unmapped.add(rid)
        members, member_errors = collect_members(args.org_id, args.directory_id, group_id, args.token, args.max_pages)
        group_diag["member_rows"] = len(members)
        diag["member_rows_seen"] += len(members)
        group_diag["errors"].extend(member_errors)
        diag["candidate_groups"].append(group_diag)

    diag["role_resource_ids_seen"] = sorted(all_resource_ids)
    diag["mapped_resource_ids"] = sorted(mapped)
    diag["unmapped_resource_ids"] = sorted(unmapped)

    if diag["groups_seen"] == 0:
        diag["conclusion"] = "groups_api_returned_zero_groups"
    elif diag["role_assignment_rows_seen"] == 0:
        diag["conclusion"] = "groups_seen_but_no_role_assignments_seen"
    elif len(mapped) == 0:
        diag["conclusion"] = "role_assignments_seen_but_no_resource_ids_mapped_to_monitored_sites"
    elif diag["member_rows_seen"] == 0:
        diag["conclusion"] = "mapped_roles_seen_but_no_group_members_seen"
    else:
        diag["conclusion"] = "diagnostics_found_candidate_group_expansion_data"

    write_json(OUT, diag)
    lines = [
        "# Group Expansion Diagnostics v1.1",
        "",
        f"Generated: {diag['generated_at_utc']}",
        f"Conclusion: **{diag['conclusion']}**",
        "",
        f"Groups seen: {diag['groups_seen']}",
        f"Probable Jira groups seen: {diag['probable_jira_groups_seen']}",
        f"Role assignment rows seen: {diag['role_assignment_rows_seen']}",
        f"Mapped resource IDs: {len(diag['mapped_resource_ids'])}",
        f"Unmapped resource IDs: {len(diag['unmapped_resource_ids'])}",
        f"Member rows seen: {diag['member_rows_seen']}",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"conclusion": diag["conclusion"], "groups_seen": diag["groups_seen"], "role_rows": diag["role_assignment_rows_seen"], "mapped_resource_ids": len(mapped), "member_rows": diag["member_rows_seen"], "output": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
