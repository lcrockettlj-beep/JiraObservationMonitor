
from typing import Dict, List, Any


def has_any_activity(user: Dict[str, Any]) -> bool:
    for key, value in user.items():
        if "Last seen in" in key:
            if value and value != "Never accessed":
                return True
    return False


def has_jira_access(user: Dict[str, Any], site_key: str) -> bool:
    return user.get(site_key) == "User"


def has_jira_activity(user: Dict[str, Any], last_seen_key: str) -> bool:
    value = user.get(last_seen_key)
    return value and value != "Never accessed"


def calculate_site_users(users: List[Dict[str, Any]], site: str):
    site_key = f"Jira - {site}"
    last_seen_key = f"Last seen in Jira - {site}"

    total = set()
    active = set()
    inactive = set()

    for u in users:
        uid = u.get("User id") or u.get("Atlassian ID") or u.get("email")
        if has_jira_access(u, site_key):
            total.add(uid)
            if has_jira_activity(u, last_seen_key):
                active.add(uid)
            else:
                inactive.add(uid)

    return {
        "total_users": len(total),
        "active_users": len(active),
        "inactive_users": len(inactive),
    }


def calculate_estate_users(users: List[Dict[str, Any]]):
    total = set()
    active = set()
    inactive = set()
    no_access = set()

    for u in users:
        uid = u.get("User id") or u.get("Atlassian ID") or u.get("email")
        total.add(uid)

        has_access = any(v == "User" for k, v in u.items() if k.startswith("Jira - "))
        has_activity = has_any_activity(u)

        if has_activity:
            active.add(uid)
        else:
            inactive.add(uid)

        if not has_access:
            no_access.add(uid)

    return {
        "total_users": len(total),
        "active_users": len(active),
        "inactive_users": len(inactive),
        "no_site_access": len(no_access),
    }
