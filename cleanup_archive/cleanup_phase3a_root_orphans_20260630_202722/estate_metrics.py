from typing import Any, Dict, List, Optional
from user_license import calculate_site_users, calculate_estate_users
from tier_engine import generate_tier_metrics

TRACKED_JIRA_SITES = [
    "gli-it-project",
    "gli-delivery-tm",
    "gli-global-technology",
]

SITE_CONFIG = [
    {"key": "gli-it-project", "site_name": "GLI IT Project", "licence_model": "tiered", "tier": 100, "licensed": 58},
    {"key": "gli-delivery-tm", "site_name": "GLI Delivery TM", "licence_model": "tiered", "tier": 50, "licensed": 28},
    {"key": "gli-global-technology", "site_name": "GLI Global Technology", "licence_model": "seat_paid", "tier": None, "licensed": 53},
]


def _uid(row: Dict[str, Any]) -> Optional[str]:
    return row.get("User id") or row.get("Atlassian ID") or row.get("email") or row.get("Email")


def _has_text(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text != "" and text.lower() != "none"


def _split_multi_value(value: Any) -> List[str]:
    if not _has_text(value):
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _unique_count(rows: List[Dict[str, Any]], column_name: str, id_key: str) -> int:
    values = set()
    for row in rows:
        if _has_text(row.get(column_name)):
            uid = row.get(id_key)
            if uid:
                values.add(uid)
    return len(values)


def _status_count(rows: List[Dict[str, Any]], status_key: str, expected_statuses, id_key: str) -> int:
    expected = {s.lower() for s in expected_statuses}
    values = set()
    for row in rows:
        status = str(row.get(status_key, "")).strip().lower()
        if status in expected:
            uid = row.get(id_key)
            if uid:
                values.add(uid)
    return len(values)


def _build_org_product_breakdown(managed_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not managed_rows:
        return []

    id_key = "Atlassian ID"
    product_columns = [
        ("Jira", "Jira"),
        ("Bitbucket", "Bitbucket"),
        ("Confluence", "Confluence"),
        ("Confluence Guest", "Confluence Guest"),
        ("Jira Work Management", "Jira Work Management"),
        ("Jira Service Management", "Jira Service Management"),
        ("Jira Product Discovery", "Jira Product Discovery"),
        ("Trello", "Trello"),
        ("Opsgenie", "Opsgenie"),
        ("Statuspage", "Statuspage"),
        ("Loom", "Loom"),
        ("Feedback", "Feedback"),
    ]

    available_columns = set(managed_rows[0].keys())
    breakdown = []

    for label, column_name in product_columns:
        if column_name not in available_columns:
            continue
        count = _unique_count(managed_rows, column_name, id_key)
        if count > 0:
            breakdown.append({"key": column_name, "label": label, "count": count})

    breakdown.sort(key=lambda item: (-item["count"], item["label"]))
    return breakdown


def _build_users_export_access_breakdown(users_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not users_rows:
        return []

    id_key = "User id"
    meta_cols = {"Group id", "Group name", "User id", "User name", "email", "User status", "Added to org", "Org role"}
    breakdown = []

    for column in users_rows[0].keys():
        if column in meta_cols:
            continue
        if column.startswith("Last seen in "):
            continue

        count = _unique_count(users_rows, column, id_key)
        if count > 0:
            breakdown.append({"key": column, "label": column, "count": count})

    breakdown.sort(key=lambda item: (-item["count"], item["label"]))
    return breakdown


def _has_tracked_jira_access(row: Dict[str, Any]) -> bool:
    for site in TRACKED_JIRA_SITES:
        if str(row.get(f"Jira - {site}", "")).strip() == "User":
            return True
    return False


def _tracked_jira_no_access_count(users_rows: List[Dict[str, Any]]) -> int:
    no_access = set()
    for row in users_rows:
        uid = _uid(row)
        if not uid:
            continue
        if not _has_tracked_jira_access(row):
            no_access.add(uid)
    return len(no_access)


def _bitbucket_only_count(users_rows: List[Dict[str, Any]]) -> int:
    values = set()
    for row in users_rows:
        uid = _uid(row)
        if not uid:
            continue

        has_tracked_jira = _has_tracked_jira_access(row)
        has_bitbucket = any(key.startswith("Bitbucket - ") and str(value).strip() == "User" for key, value in row.items())

        if has_bitbucket and not has_tracked_jira:
            values.add(uid)

    return len(values)


def _site_extra_access_count(users_rows: List[Dict[str, Any]], app_label: str, site_key: str) -> int:
    if not users_rows:
        return 0

    column_name = f"{app_label} - {site_key}"
    if column_name not in users_rows[0]:
        return 0

    return _unique_count(users_rows, column_name, "User id")


def _find_users_for_managed_status(managed_rows: List[Dict[str, Any]], statuses) -> List[Dict[str, Any]]:
    expected = {s.lower() for s in statuses}
    items = []
    seen = set()

    for row in managed_rows:
        uid = _uid(row)
        status = str(row.get("Status", "")).strip().lower()
        if not uid or uid in seen or status not in expected:
            continue

        seen.add(uid)
        items.append({
            "name": row.get("Name", ""),
            "email": row.get("Email", ""),
            "id": uid,
            "status": row.get("Status", ""),
            "last_active": row.get("Last active date [UTC]", ""),
            "bitbucket": row.get("Bitbucket", ""),
            "jira": row.get("Jira", ""),
            "confluence": row.get("Confluence", ""),
        })

    items.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("email", "")).lower()))
    return items


def _find_users_for_org_product(managed_rows: List[Dict[str, Any]], product_key: str) -> List[Dict[str, Any]]:
    items = []
    seen = set()

    for row in managed_rows:
        uid = _uid(row)
        if not uid or uid in seen:
            continue
        if not _has_text(row.get(product_key)):
            continue

        seen.add(uid)
        raw_value = row.get(product_key, "")
        items.append({
            "name": row.get("Name", ""),
            "email": row.get("Email", ""),
            "id": uid,
            "status": row.get("Status", ""),
            "last_active": row.get("Last active date [UTC]", ""),
            "product_value": raw_value,
            "product_sites": _split_multi_value(raw_value),
        })

    items.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("email", "")).lower()))
    return items


def _find_users_for_access_column(users_rows: List[Dict[str, Any]], access_column: str) -> List[Dict[str, Any]]:
    items = []
    seen = set()
    last_seen_column = None

    if access_column.startswith("Jira - "):
        site = access_column.replace("Jira - ", "", 1)
        last_seen_column = f"Last seen in Jira - {site}"
    elif access_column.startswith("Confluence - "):
        site = access_column.replace("Confluence - ", "", 1)
        last_seen_column = f"Last seen in Confluence - {site}"
    elif access_column.startswith("Bitbucket - "):
        site = access_column.replace("Bitbucket - ", "", 1)
        last_seen_column = f"Last seen in Bitbucket - {site}"

    for row in users_rows:
        uid = _uid(row)
        if not uid or uid in seen:
            continue
        if str(row.get(access_column, "")).strip() != "User":
            continue

        seen.add(uid)
        items.append({
            "name": row.get("User name", ""),
            "email": row.get("email", ""),
            "id": uid,
            "status": row.get("User status", ""),
            "last_active": row.get(last_seen_column, "") if last_seen_column else "",
            "access_value": row.get(access_column, ""),
        })

    items.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("email", "")).lower()))
    return items


def _find_users_with_no_tracked_jira(users_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    seen = set()

    for row in users_rows:
        uid = _uid(row)
        if not uid or uid in seen:
            continue
        if _has_tracked_jira_access(row):
            continue

        seen.add(uid)
        items.append({
            "name": row.get("User name", ""),
            "email": row.get("email", ""),
            "id": uid,
            "status": row.get("User status", ""),
            "last_active": "",
        })

    items.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("email", "")).lower()))
    return items


def _find_inactive_without_site_access(users_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    seen = set()

    for row in users_rows:
        uid = _uid(row)
        if not uid or uid in seen:
            continue

        user_status = str(row.get("User status", "")).strip().lower()
        if user_status != "inactive":
            continue

        if _has_tracked_jira_access(row):
            continue

        seen.add(uid)
        items.append({
            "name": row.get("User name", ""),
            "email": row.get("email", ""),
            "id": uid,
            "status": row.get("User status", ""),
        })

    items.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("email", "")).lower()))
    return items


def _find_bitbucket_only_no_tracked_jira(users_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
    seen = set()

    for row in users_rows:
        uid = _uid(row)
        if not uid or uid in seen:
            continue

        has_tracked_jira = _has_tracked_jira_access(row)
        has_bitbucket = any(key.startswith("Bitbucket - ") and str(value).strip() == "User" for key, value in row.items())

        if not (has_bitbucket and not has_tracked_jira):
            continue

        seen.add(uid)
        items.append({
            "name": row.get("User name", ""),
            "email": row.get("email", ""),
            "id": uid,
            "status": row.get("User status", ""),
            "last_active": "",
        })

    items.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("email", "")).lower()))
    return items


def _find_site_specific_users(users_rows: List[Dict[str, Any]], site_key: str) -> List[Dict[str, Any]]:
    items = []
    seen = set()

    jira_col = f"Jira - {site_key}"
    jira_last_seen = f"Last seen in Jira - {site_key}"
    confluence_col = f"Confluence - {site_key}"
    confluence_last_seen = f"Last seen in Confluence - {site_key}"
    atlas_col = f"Atlas - {site_key}"
    goals_col = f"Goals - {site_key}"
    projects_col = f"Projects - {site_key}"

    for row in users_rows:
        uid = _uid(row)
        if not uid or uid in seen:
            continue
        if str(row.get(jira_col, "")).strip() != "User":
            continue

        seen.add(uid)
        items.append({
            "name": row.get("User name", ""),
            "email": row.get("email", ""),
            "id": uid,
            "status": row.get("User status", ""),
            "jira_last_seen": row.get(jira_last_seen, ""),
            "confluence_access": row.get(confluence_col, ""),
            "confluence_last_seen": row.get(confluence_last_seen, ""),
            "atlas_access": row.get(atlas_col, ""),
            "goals_access": row.get(goals_col, ""),
            "projects_access": row.get(projects_col, ""),
        })

    items.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("email", "")).lower()))
    return items


def _build_site_operational_status(site_record: Dict[str, Any]) -> Dict[str, Any]:
    licence_model = site_record.get("licence_model")
    inactive_users = site_record.get("inactive_users", 0) or 0
    confluence_users = site_record.get("confluence_users", 0) or 0

    if licence_model == "seat_paid":
        reason_lines = ["Seat-paid model — tier usage warnings do not apply at present."]
        if inactive_users > 0:
            reason_lines.append(f"{inactive_users} inactive Jira user(s) still have access.")
        if confluence_users > 0:
            reason_lines.append(f"{confluence_users} Confluence user(s) overlap with this site.")
        return {
            "status": "stable",
            "reason": "Seat-paid model — tier warnings not applicable at present.",
            "reason_lines": reason_lines,
            "atlassian_area": "Billing / User access",
        }

    tier_status = site_record.get("tier_status", "stable")
    usage_percent = site_record.get("usage_percent", 0)
    capacity_remaining = site_record.get("capacity_remaining", 0)

    if tier_status == "critical":
        reason_lines = [f"Tier capacity is effectively full ({usage_percent}% used, {capacity_remaining} remaining)."]
        if inactive_users > 0:
            reason_lines.append(f"{inactive_users} inactive Jira user(s) still have access.")
        if confluence_users > 0:
            reason_lines.append(f"{confluence_users} Confluence user(s) overlap with this site.")
        return {
            "status": "critical",
            "reason": f"Tier capacity is full ({usage_percent}% used).",
            "reason_lines": reason_lines,
            "atlassian_area": "Billing / User access",
        }

    if tier_status == "warning":
        reason_lines = [f"Tier usage is approaching limit ({usage_percent}% used, {capacity_remaining} remaining)."]
        if inactive_users > 0:
            reason_lines.append(f"{inactive_users} inactive Jira user(s) still have access.")
        if confluence_users > 0:
            reason_lines.append(f"{confluence_users} Confluence user(s) overlap with this site.")
        return {
            "status": "warning",
            "reason": f"Tier usage is approaching limit ({usage_percent}% used).",
            "reason_lines": reason_lines,
            "atlassian_area": "Billing / User access",
        }

    reason_lines = [f"Tier usage currently has headroom ({usage_percent}% used, {capacity_remaining} remaining)."]
    if inactive_users > 0:
        reason_lines.append(f"{inactive_users} inactive Jira user(s) still have access.")
    if confluence_users > 0:
        reason_lines.append(f"{confluence_users} Confluence user(s) overlap with this site.")
    return {
        "status": "stable",
        "reason": f"Tier usage currently has headroom ({usage_percent}% used).",
        "reason_lines": reason_lines,
        "atlassian_area": "Billing / User access",
    }


def build_estate_metrics(users_rows: List[Dict[str, Any]], managed_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    site_results = []

    for site in SITE_CONFIG:
        site_key = site["key"]
        licence_model = site["licence_model"]

        users_data = calculate_site_users(users_rows, site_key)

        if licence_model == "tiered":
            tier_data = generate_tier_metrics(site["licensed"], site["tier"])
        else:
            tier_data = {
                "licensed_users": site["licensed"],
                "tier_limit": None,
                "usage_percent": None,
                "capacity_remaining": None,
                "tier_status": "not_applicable",
            }

        site_result = {
            "site": site_key,
            "site_name": site["site_name"],
            "licence_model": licence_model,
            **users_data,
            **tier_data,
            "confluence_users": _site_extra_access_count(users_rows, "Confluence", site_key),
            "atlas_users": _site_extra_access_count(users_rows, "Atlas", site_key),
            "goals_users": _site_extra_access_count(users_rows, "Goals", site_key),
            "projects_users": _site_extra_access_count(users_rows, "Projects", site_key),
        }

        site_result.update(_build_site_operational_status(site_result))
        site_results.append(site_result)

    critical_sites = [s for s in site_results if s["status"] == "critical"]
    warning_sites = [s for s in site_results if s["status"] == "warning"]
    stable_sites = [s for s in site_results if s["status"] == "stable"]

    activity = calculate_estate_users(users_rows)

    managed_total_users = len({_uid(r) for r in managed_rows if _uid(r)}) if managed_rows else 0
    managed_active_accounts = _status_count(managed_rows, "Status", {"active"}, "Atlassian ID") if managed_rows else 0
    managed_disabled_accounts = _status_count(managed_rows, "Status", {"disabled", "deactivated"}, "Atlassian ID") if managed_rows else 0

    org_product_breakdown = _build_org_product_breakdown(managed_rows)
    users_export_breakdown = _build_users_export_access_breakdown(users_rows)
    inactive_without_site_access_rows = _find_inactive_without_site_access(users_rows)

    drilldowns = {
        "managed_disabled_accounts": {
            "title": "Managed Disabled Accounts",
            "reason": "These managed accounts are disabled and should be reviewed for cleanup, ownership, and product access impact.",
            "atlassian_area": "Atlassian Administration → Directory → Managed accounts",
            "columns": ["name", "email", "status", "last_active", "jira", "confluence", "bitbucket"],
            "rows": _find_users_for_managed_status(managed_rows, {"disabled", "deactivated"}),
        },
        "no_tracked_jira": {
            "title": "No Tracked Jira Site Access",
            "reason": "These users exist in the organisation export but do not have access to any of the three tracked Jira sites.",
            "atlassian_area": "Atlassian Administration → Directory → Users / App access",
            "columns": ["name", "email", "status", "id"],
            "rows": _find_users_with_no_tracked_jira(users_rows),
        },
        
        
        "inactive_without_site_access": {
            "title": "Inactive Without Tracked Site Access",
            "reason": "These users are marked inactive in the users export and do not have access to any of the three currently tracked Jira sites. This reflects the current monitored Jira scope only.",
            "atlassian_area": "Atlassian Administration → Directory → Users / App access",
            "columns": ["name", "email", "status", "id"],
            "rows": inactive_without_site_access_rows,
        },


        "bitbucket_only_no_tracked_jira": {
            "title": "Bitbucket Only / No Tracked Jira",
            "reason": "These users have Bitbucket access but no access to the tracked Jira sites, which can indicate non-Jira usage or access drift.",
            "atlassian_area": "Atlassian Administration → Directory → Users / App access",
            "columns": ["name", "email", "status", "id"],
            "rows": _find_bitbucket_only_no_tracked_jira(users_rows),
        },
    }

    for site in SITE_CONFIG:
        key = f"site::{site['key']}"
        drilldowns[key] = {
            "title": f"Site Users — {site['site_name']}",
            "reason": "These users have explicit Jira access to this tracked site. Use this list to inspect activity and product overlap before actioning in Atlassian.",
            "atlassian_area": "Atlassian Administration → Directory → Users / App access or Site user management",
            "columns": ["name", "email", "status", "jira_last_seen", "confluence_access", "confluence_last_seen", "atlas_access", "goals_access", "projects_access"],
            "rows": _find_site_specific_users(users_rows, site["key"]),
        }

    for item in org_product_breakdown:
        key = f"product::{item['key']}"
        drilldowns[key] = {
            "title": f"Organisation Product Breakdown — {item['label']}",
            "reason": f"These users have organisation-level access recorded for {item['label']}.",
            "atlassian_area": "Atlassian Administration → Directory → Users / App access",
            "columns": ["name", "email", "status", "last_active", "product_sites"],
            "rows": _find_users_for_org_product(managed_rows, item["key"]),
        }

    for item in users_export_breakdown:
        key = f"access::{item['key']}"
        drilldowns[key] = {
            "title": f"Users Export Access Breakdown — {item['label']}",
            "reason": f"These users have explicit access in the users export for {item['label']}.",
            "atlassian_area": "Atlassian Administration → Directory → Users / App access",
            "columns": ["name", "email", "status", "last_active", "access_value"],
            "rows": _find_users_for_access_column(users_rows, item["key"]),
        }

    estate = {
        "organisation_users": managed_total_users,
        "managed_active_accounts": managed_active_accounts,
        "managed_disabled_accounts": managed_disabled_accounts,
        "observed_total_users": activity.get("total_users", 0),
        "observed_active_users": activity.get("active_users", 0),
        "observed_inactive_users": activity.get("inactive_users", 0),
        "no_tracked_jira_site_access": _tracked_jira_no_access_count(users_rows),
        "inactive_without_site_access": len(inactive_without_site_access_rows),
        "bitbucket_only_no_tracked_jira": _bitbucket_only_count(users_rows),
        "critical_site_count": len(critical_sites),
        "warning_site_count": len(warning_sites),
        "stable_site_count": len(stable_sites),
    }

    return {
        "estate": estate,
        "sites": site_results,
        "critical_sites": critical_sites,
        "warning_sites": warning_sites,
        "stable_sites": stable_sites,
        "org_product_breakdown": org_product_breakdown,
        "users_export_breakdown": users_export_breakdown,
        "drilldowns": drilldowns,
    }