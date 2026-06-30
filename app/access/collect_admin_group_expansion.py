import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "data" / "admin_group_expansion.json"
STATUS = ROOT / "static" / "data" / "admin_group_expansion_status.json"
SITE_REGISTRY = ROOT / "static" / "data" / "site_registry.json"
API_BASE = "https://api.atlassian.com"
ARI_SITE_RE = re.compile(r"^ari:cloud:(?P<product>[^:]+)::site/(?P<site_id>[^/]+)$", re.IGNORECASE)


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


def guarded(reason, status="unavailable", extra=None):
    payload = {
        "schema": "jom-admin-group-expansion-v1.2",
        "generated_at_utc": now_utc(),
        "source_status": status,
        "safe_to_use_for_named_access": False,
        "reason": reason,
        "groups": [],
        "summary": {"group_count": 0, "product_group_count": 0, "member_assignment_count": 0, "mapped_site_count": 0},
    }
    if extra:
        payload["details"] = extra
    write_json(OUT, payload)
    write_json(STATUS, {"schema": "jom-admin-group-expansion-status-v1.2", "generated_at_utc": now_utc(), "overall_status": status, "safe_to_use_for_named_access": False, "reason": reason, "output": str(OUT), "details": extra or {}})
    print(json.dumps({"source_status": status, "safe": False, "reason": reason, "output": str(OUT)}, indent=2))
    return 0


def request_json(url, token, method="GET", body=None):
    data = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def page_get(url, token, data_key="data", max_pages=100):
    rows = []
    next_url = url
    pages = 0
    while next_url and pages < max_pages:
        pages += 1
        payload = request_json(next_url, token)
        page_rows = payload.get(data_key)
        if isinstance(page_rows, list):
            rows.extend(page_rows)
        elif isinstance(payload.get("values"), list):
            rows.extend(payload.get("values"))
        links = payload.get("links") or {}
        next_link = links.get("next") if isinstance(links, dict) else None
        if isinstance(next_link, dict):
            next_url = next_link.get("href")
        elif isinstance(next_link, str) and next_link.startswith("http"):
            next_url = next_link
        elif isinstance(next_link, str) and next_link.startswith("/"):
            next_url = API_BASE + next_link
        else:
            next_url = None
        time.sleep(0.05)
    return rows


def add_mapping(mappings, key, site_key):
    if key and site_key:
        mappings[str(key)] = str(site_key)


def ari_variants(site_id):
    if not site_id:
        return []
    return [
        f"ari:cloud:jira::site/{site_id}",
        f"ari:cloud:jira-software::site/{site_id}",
        f"ari:cloud:confluence::site/{site_id}",
    ]


def monitored_resource_map():
    registry = read_json(SITE_REGISTRY, {}) or {}
    mappings = {}
    monitored_site_keys = set()
    monitored_sites = []
    for site in registry.get("sites", []):
        if str(site.get("classification") or "").lower() != "monitored":
            continue
        site_key = site.get("site_key") or site.get("site_name") or site.get("name") or site.get("url") or site.get("site_url")
        if site_key:
            monitored_site_keys.add(str(site_key))
        cloud_id = site.get("cloud_id") or site.get("resource_id") or site.get("id") or site.get("site_id")
        monitored_sites.append({"site_key": site_key, "cloud_id": cloud_id, "url": site.get("url") or site.get("site_url")})
        for field in ("cloud_id", "resource_id", "id", "site_id", "url", "site_url", "site_key", "site_name", "name"):
            add_mapping(mappings, site.get(field), site_key)
        if cloud_id:
            for variant in ari_variants(cloud_id):
                add_mapping(mappings, variant, site_key)
        for nested_field in ("resource", "cloud", "atlassian_resource"):
            nested = site.get(nested_field)
            if isinstance(nested, dict):
                nested_id = nested.get("id") or nested.get("cloudId") or nested.get("cloud_id")
                for field in ("id", "cloudId", "cloud_id", "url", "name"):
                    add_mapping(mappings, nested.get(field), site_key)
                if nested_id:
                    for variant in ari_variants(nested_id):
                        add_mapping(mappings, variant, site_key)
    return mappings, monitored_site_keys, monitored_sites


def normalise_resource_candidates(resource_id):
    values = set()
    if not resource_id:
        return values
    text = str(resource_id)
    values.add(text)
    match = ARI_SITE_RE.match(text)
    if match:
        site_id = match.group("site_id")
        values.add(site_id)
        for variant in ari_variants(site_id):
            values.add(variant)
    return values


def map_resource(resource_id, mappings):
    for candidate in normalise_resource_candidates(resource_id):
        if candidate in mappings:
            return mappings[candidate]
    return None


def extract_group_id(group):
    return str(group.get("id") or group.get("groupId") or group.get("uuid") or "")


def extract_group_name(group):
    return str(group.get("name") or group.get("displayName") or group.get("groupName") or extract_group_id(group))


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


def extract_product(role):
    text = " ".join(str(role.get(k) or "") for k in ("product", "productKey", "resourceType", "role", "roleKey", "name", "type")).lower()
    for rid in extract_role_resource_ids(role):
        if "jira-software" in rid.lower() or "jira::site" in rid.lower():
            return "jira-software"
    if "jira" in text:
        return "jira-software"
    if "confluence" in text:
        return "confluence"
    return "unknown"


def collect_members_by_memberships(org_id, directory_id, group_id, token):
    url = f"{API_BASE}/admin/v2/orgs/{org_id}/directories/{directory_id}/groups/{group_id}/memberships?limit=100"
    try:
        rows = page_get(url, token)
    except Exception as exc:
        return [], str(exc)
    members = []
    for row in rows:
        if isinstance(row, dict):
            account_id = row.get("accountId") or row.get("account_id") or row.get("id") or row.get("userId")
            if account_id:
                members.append({"account_id": str(account_id), "source": "group_memberships_endpoint"})
    return members, ""


def collect_members_by_users_filter(org_id, directory_id, group_id, token):
    query = urllib.parse.urlencode({"limit": 100, "groupIds": group_id})
    url = f"{API_BASE}/admin/v2/orgs/{org_id}/directories/{directory_id}/users?{query}"
    try:
        rows = page_get(url, token)
    except Exception as exc:
        return [], str(exc)
    members = []
    for row in rows:
        if isinstance(row, dict):
            account_id = row.get("accountId") or row.get("account_id") or row.get("id")
            if account_id:
                members.append({"account_id": str(account_id), "source": "users_groupIds_filter"})
    return members, ""


def main():
    parser = argparse.ArgumentParser(description="Collect Atlassian group-derived product access for JOM named access recovery with ARI site mapping.")
    parser.add_argument("--org-id", default=os.getenv("ATLASSIAN_ORG_ID") or os.getenv("ATLASSIAN_ADMIN_ORG_ID") or "")
    parser.add_argument("--directory-ids", default=os.getenv("ATLASSIAN_DIRECTORY_IDS") or os.getenv("ATLASSIAN_DIRECTORY_ID", ""))
    parser.add_argument("--token", default=os.getenv("ATLASSIAN_ADMIN_TOKEN") or os.getenv("ATLASSIAN_ADMIN_API_KEY") or "")
    parser.add_argument("--max-groups", type=int, default=int(os.getenv("JOM_GROUP_EXPANSION_MAX_GROUPS", "500")))
    args = parser.parse_args()

    if not args.token:
        return guarded("ATLASSIAN_ADMIN_TOKEN / ATLASSIAN_ADMIN_API_KEY is not set. Cannot collect group-derived product access.")
    if not args.org_id:
        return guarded("ATLASSIAN_ORG_ID / ATLASSIAN_ADMIN_ORG_ID is not set. Cannot collect group-derived product access.")
    directory_ids = [part.strip() for part in str(args.directory_ids or "").split(",") if part.strip()]
    if not directory_ids:
        return guarded("ATLASSIAN_DIRECTORY_ID or ATLASSIAN_DIRECTORY_IDS is not set. Admin v2 group APIs are directory-scoped.")

    resource_map, monitored_site_keys, monitored_sites = monitored_resource_map()
    collected_groups = []
    errors = []
    diagnostics = {"monitored_sites": monitored_sites, "resource_map_key_count": len(resource_map), "unmapped_role_resource_ids": []}
    unmapped_role_resource_ids = set()

    for directory_id in directory_ids:
        groups_url = f"{API_BASE}/admin/v2/orgs/{args.org_id}/directories/{directory_id}/groups?limit=100"
        try:
            groups = page_get(groups_url, args.token)
        except Exception as exc:
            errors.append({"directory_id": directory_id, "stage": "groups", "error": str(exc)})
            continue
        for group in groups[:args.max_groups]:
            group_id = extract_group_id(group)
            group_name = extract_group_name(group)
            if not group_id:
                continue
            roles_url = f"{API_BASE}/admin/v2/orgs/{args.org_id}/directories/{directory_id}/groups/{group_id}/role-assignments?limit=100"
            try:
                roles = page_get(roles_url, args.token)
            except Exception as exc:
                errors.append({"directory_id": directory_id, "group_id": group_id, "group_name": group_name, "stage": "role_assignments", "error": str(exc)})
                roles = []
            mapped_sites = set()
            products = set()
            raw_resource_ids = set()
            for role in roles:
                if not isinstance(role, dict):
                    continue
                product = extract_product(role)
                products.add(product)
                for resource_id in extract_role_resource_ids(role):
                    raw_resource_ids.add(resource_id)
                    mapped = map_resource(resource_id, resource_map)
                    if mapped:
                        mapped_sites.add(mapped)
                    elif "jira" in resource_id.lower():
                        unmapped_role_resource_ids.add(resource_id)
            if not mapped_sites or not any(product.startswith("jira") for product in products):
                continue
            members, member_error = collect_members_by_memberships(args.org_id, directory_id, group_id, args.token)
            if not members:
                fallback_members, fallback_error = collect_members_by_users_filter(args.org_id, directory_id, group_id, args.token)
                members = fallback_members
                if member_error and fallback_error:
                    errors.append({"directory_id": directory_id, "group_id": group_id, "group_name": group_name, "stage": "members", "error": f"memberships={member_error}; users_filter={fallback_error}"})
            if not members:
                errors.append({"directory_id": directory_id, "group_id": group_id, "group_name": group_name, "stage": "members", "error": "No members returned for mapped product group."})
                continue
            collected_groups.append({
                "group_id": group_id,
                "group_name": group_name,
                "directory_id": directory_id,
                "product": "jira-software",
                "sites": sorted(mapped_sites),
                "raw_resource_ids": sorted(raw_resource_ids),
                "members": sorted(members, key=lambda item: item.get("account_id", "")),
                "member_count": len(members),
                "source": "atlassian_admin_v2_groups_role_assignments_memberships_ari_mapping_v1_2",
            })

    member_assignment_count = sum(len(group.get("members", [])) * len(group.get("sites", [])) for group in collected_groups)
    mapped_site_count = len({site for group in collected_groups for site in group.get("sites", [])})
    diagnostics["unmapped_role_resource_ids"] = sorted(unmapped_role_resource_ids)
    safe = bool(collected_groups and member_assignment_count > 0)
    payload = {
        "schema": "jom-admin-group-expansion-v1.2",
        "generated_at_utc": now_utc(),
        "source_status": "generated" if safe else "unavailable",
        "safe_to_use_for_named_access": safe,
        "reason": "Group-derived Jira product access collected from Atlassian Admin v2 APIs with ARI site mapping." if safe else "No safe group-derived Jira product access assignments were collected after ARI site mapping.",
        "org_id": args.org_id,
        "directory_ids": directory_ids,
        "summary": {"group_count": len(collected_groups), "product_group_count": len(collected_groups), "member_assignment_count": member_assignment_count, "mapped_site_count": mapped_site_count, "error_count": len(errors)},
        "diagnostics": diagnostics,
        "errors": errors[:100],
        "groups": collected_groups,
    }
    write_json(OUT, payload)
    write_json(STATUS, {"schema": "jom-admin-group-expansion-status-v1.2", "generated_at_utc": now_utc(), "overall_status": "ok" if safe else "attention", "safe_to_use_for_named_access": safe, "summary": payload["summary"], "output": str(OUT)})
    print(json.dumps({"source_status": payload["source_status"], "safe": safe, "groups": len(collected_groups), "member_assignment_count": member_assignment_count, "mapped_site_count": mapped_site_count, "output": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
