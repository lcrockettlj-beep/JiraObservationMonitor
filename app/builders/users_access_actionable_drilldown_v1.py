from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API_HOST = "https://api.atlassian.com"
DIRECTORY_AUTHORITY = Path("runtime/data/admin_directory_users.json")
IDENTITY_AUTHORITY = Path("runtime/data/named_user_display_identity_v1.json")
USER_FOOTPRINT = Path("runtime/data/user_footprint.json")
OUTPUT_RELATIVE = Path("runtime/data/users_access_actionable_drilldown_v1.json")
MAXIMUM_AGE_HOURS = 26
AUTHORIZED_ROLE = "Organisation administrator"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_env(root: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env_file = root / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def request_json(url: str, token: str) -> Tuple[int, Any]:
    request = urllib.request.Request(url=url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code, {}
    except Exception:
        return 0, {}


def rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "values", "users", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def next_url(payload: Any, current_url: str) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
    value = links.get("next") or payload.get("next") or payload.get("nextPage")
    if isinstance(value, str) and value.strip():
        value = value.strip()
        if value.startswith(("http://", "https://", "/", "?")):
            return urllib.parse.urljoin(current_url, value)
        parsed = urllib.parse.urlsplit(current_url)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        query["cursor"] = [value]
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query, doseq=True), parsed.fragment))
    cursor = payload.get("nextCursor") or payload.get("next_cursor")
    if not cursor and isinstance(payload.get("meta"), dict):
        cursor = payload["meta"].get("nextCursor") or payload["meta"].get("next_cursor")
    if cursor:
        parsed = urllib.parse.urlsplit(current_url)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        query["cursor"] = [str(cursor)]
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query, doseq=True), parsed.fragment))
    return None


def collect(url: str, token: str, max_pages: int = 1000) -> Tuple[List[Dict[str, Any]], int, bool, Counter]:
    output: List[Dict[str, Any]] = []
    statuses: Counter = Counter()
    pages = 0
    seen = set()
    current = url
    while current:
        if current in seen or pages >= max_pages:
            return output, pages, False, statuses
        seen.add(current)
        status, payload = request_json(current, token)
        statuses[status] += 1
        pages += 1
        if status != 200:
            return output, pages, False, statuses
        output.extend(rows(payload))
        current = next_url(payload, current)
    return output, pages, True, statuses


def account_id(row: Dict[str, Any]) -> str:
    return str(row.get("accountId") or row.get("account_id") or row.get("id") or row.get("userId") or "").strip()


def value(row: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if row.get(name) not in (None, ""):
            return row.get(name)
    return None


def norm(value_: Any) -> str:
    return str(value_ or "").strip().lower().replace("-", "_").replace(" ", "_")


def bool_value(value_: Any) -> Optional[bool]:
    if isinstance(value_, bool):
        return value_
    text = norm(value_)
    if text in {"true", "yes", "enabled", "1"}:
        return True
    if text in {"false", "no", "disabled", "0"}:
        return False
    return None


def list_strings(value_: Any) -> List[str]:
    if not isinstance(value_, list):
        return []
    output = []
    for item in value_:
        if isinstance(item, str) and item.strip():
            output.append(item.strip())
        elif isinstance(item, dict):
            label = value(item, "key", "name", "role", "roleKey", "role_key", "type")
            if label:
                output.append(str(label).strip())
    return sorted(set(output))


def role_kind(role: str) -> Optional[str]:
    text = norm(role)
    if "org_admin" in text or "organisation_admin" in text or "organization_admin" in text:
        return "organisation_administrators"
    if "site_admin" in text or "site_administrator" in text:
        return "site_administrators"
    if "user_access_admin" in text or "user_access_administrator" in text:
        return "user_access_administrators"
    return None


def identity_map(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    output = {}
    for row in payload.get("users", []) if isinstance(payload.get("users"), list) else []:
        if isinstance(row, dict) and account_id(row):
            output[account_id(row)] = row
    return output


def footprint_map(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    output = {}
    for row in payload.get("users", []) if isinstance(payload.get("users"), list) else []:
        if isinstance(row, dict) and account_id(row):
            output[account_id(row)] = row
    return output


def high_concentration(row: Dict[str, Any]) -> bool:
    # user_footprint.json proves the per-user concentration classification in users[].category.
    # Keep legacy candidate fields as compatible fallbacks, but category is the authority owner.
    explicit = norm(value(row, "category", "access_concentration", "concentration", "concentration_level", "duplication_level", "access_level", "risk_level"))
    return explicit in {"high", "high_access_concentration", "high_concentration"}


def record(account: str, directory_row: Dict[str, Any], identities: Dict[str, Dict[str, Any]], footprint: Dict[str, Dict[str, Any]], reason: str, action: str, management_url: str) -> Dict[str, Any]:
    identity = identities.get(account, {})
    foot = footprint.get(account, {})
    display_name = str(identity.get("display_name") or value(directory_row, "displayName", "name") or "Unavailable").strip()
    sites = identity.get("sites") if isinstance(identity.get("sites"), list) else foot.get("sites") if isinstance(foot.get("sites"), list) else []
    return {
        "account_id": account,
        "display_name": display_name,
        "account_status": norm(value(directory_row, "status", "membershipStatus", "accountStatus")) or "unknown",
        "sites": sorted({str(item).strip() for item in sites if str(item).strip()}),
        "site_count": int(identity.get("site_count") or foot.get("site_count") or len(sites)),
        "product_access_assignments": int(identity.get("product_access_assignments") or foot.get("product_access_assignments") or 0),
        "reason": reason,
        "recommended_action": action,
        "management_url": management_url,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build actionable Users & Access drill-down authority.")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    if not (root / "app").exists() or not (root / "runtime" / "data").exists():
        raise SystemExit("Run from the JiraObservationMonitor repository root.")

    env = load_env(root)
    org_id = (env.get("ATLASSIAN_ADMIN_ORG_ID") or env.get("ATLASSIAN_ORG_ID") or "").strip()
    token = (env.get("ATLASSIAN_ADMIN_API_KEY") or env.get("ATLASSIAN_ADMIN_TOKEN") or "").strip()
    if not org_id or not token:
        raise SystemExit("Missing ATLASSIAN_ADMIN_ORG_ID or ATLASSIAN_ADMIN_API_KEY")

    directory_authority = read_json(root / DIRECTORY_AUTHORITY)
    identity_authority = read_json(root / IDENTITY_AUTHORITY)
    footprint_authority = read_json(root / USER_FOOTPRINT)
    directory_ids = sorted({str(row.get("directory_id") or "").strip() for row in directory_authority.get("users", []) if isinstance(row, dict) and str(row.get("directory_id") or "").strip()})
    if not directory_ids:
        raise SystemExit("No directory ID is available from admin_directory_users.json")

    org_url = f"{API_HOST}/admin/v1/orgs/{urllib.parse.quote(org_id, safe='')}/users?limit=100"
    org_rows, org_pages, org_complete, org_statuses = collect(org_url, token)
    directory_rows: List[Dict[str, Any]] = []
    directory_pages = 0
    directory_complete = True
    directory_statuses: Counter = Counter()
    for directory_id in directory_ids:
        url = f"{API_HOST}/admin/v2/orgs/{urllib.parse.quote(org_id, safe='')}/directories/{urllib.parse.quote(directory_id, safe='')}/users?limit=100"
        collected, pages, complete, statuses = collect(url, token)
        directory_rows.extend(collected)
        directory_pages += pages
        directory_complete = directory_complete and complete
        directory_statuses.update(statuses)

    if not org_complete or not directory_complete or set(org_statuses) != {200} or set(directory_statuses) != {200}:
        print(json.dumps({"status": "unavailable", "output_unchanged": True, "reason": "Full live organisation or directory pagination failed."}, indent=2))
        return 2

    identities = identity_map(identity_authority)
    footprint = footprint_map(footprint_authority)
    org_by_id = {account_id(row): row for row in org_rows if account_id(row)}
    directory_by_id = {account_id(row): row for row in directory_rows if account_id(row)}
    users_url = f"https://admin.atlassian.com/o/{urllib.parse.quote(org_id, safe='')}/users"
    policies_url = f"https://admin.atlassian.com/o/{urllib.parse.quote(org_id, safe='')}/security/authentication-policies"
    roles_url = f"https://admin.atlassian.com/o/{urllib.parse.quote(org_id, safe='')}/admin-roles"

    categories: Dict[str, Dict[str, Any]] = {
        "mfa_disabled": {"label": "MFA disabled", "available": True, "records": [], "management_url": policies_url},
        "mfa_unknown": {"label": "MFA unknown", "available": True, "records": [], "management_url": policies_url},
        "organisation_administrators": {"label": "Organisation administrators", "available": True, "records": [], "management_url": roles_url},
        "site_administrators": {"label": "Site administrators", "available": True, "records": [], "management_url": roles_url},
        "user_access_administrators": {"label": "User access administrators", "available": True, "records": [], "management_url": roles_url},
        "high_access_concentration": {"label": "High access concentration", "available": True, "records": [], "management_url": users_url},
        "for_deletion": {"label": "For deletion", "available": True, "records": [], "management_url": users_url},
        "unmanaged_accounts": {"label": "Unmanaged accounts", "available": True, "records": [], "management_url": users_url},
        "suspended_accounts": {"label": "Suspended accounts", "available": True, "records": [], "management_url": users_url},
        "deactivated_accounts": {"label": "Deactivated accounts", "available": True, "records": [], "management_url": users_url},
        "not_invited": {"label": "Not invited", "available": False, "records": [], "reason": "The tested live APIs do not expose the Atlassian Administration not-invited state."},
    }

    for account, row in directory_by_id.items():
        mfa = bool_value(value(row, "mfaEnabled", "mfa_enabled"))
        if mfa is False:
            categories["mfa_disabled"]["records"].append(record(account, row, identities, footprint, "Directory authority reports MFA is not enabled.", "Review the approved authentication policy and account exception.", policies_url))
        elif mfa is None:
            categories["mfa_unknown"]["records"].append(record(account, row, identities, footprint, "Directory authority does not provide a proven MFA state.", "Review account security evidence in Atlassian Administration.", policies_url))
        if bool_value(value(row, "forDeletion", "for_deletion")) is True:
            categories["for_deletion"]["records"].append(record(account, row, identities, footprint, "Directory authority marks this account for deletion.", "Review or cancel the deletion within Atlassian Administration.", users_url))
        status = norm(value(row, "status", "membershipStatus", "accountStatus"))
        if status == "suspended":
            categories["suspended_accounts"]["records"].append(record(account, row, identities, footprint, "Directory membership status is suspended.", "Review the account lifecycle in Atlassian Administration.", users_url))
        if status in {"deactivated", "inactive", "closed"}:
            categories["deactivated_accounts"]["records"].append(record(account, row, identities, footprint, "Directory account status is deactivated or inactive.", "Review whether the account should remain deactivated or be deleted.", users_url))
        claim_status = norm(value(row, "claimStatus", "claim_status"))
        if claim_status in {"unmanaged", "not_managed", "external", "unclaimed"}:
            categories["unmanaged_accounts"]["records"].append(record(account, row, identities, footprint, "Directory claim status does not identify this account as managed.", "Review account claiming and managed-domain settings.", users_url))
        roles = list_strings(value(row, "platformRoles", "platform_roles", "roles"))
        for role in roles:
            kind = role_kind(role)
            if kind:
                item = record(account, row, identities, footprint, "Directory authority assigns the " + role + " role.", "Review administrative role assignment in Atlassian Administration.", roles_url)
                item["role"] = role
                categories[kind]["records"].append(item)

    for account, row in footprint.items():
        if high_concentration(row):
            directory_row = directory_by_id.get(account, org_by_id.get(account, {}))
            categories["high_access_concentration"]["records"].append(record(account, directory_row, identities, footprint, "User Footprint authority classifies this account as high access concentration.", "Review multi-site and product access for least-privilege alignment.", users_url))

    for category in categories.values():
        category["records"].sort(key=lambda item: (str(item.get("display_name") or "").casefold(), item.get("account_id") or ""))
        category["count"] = len(category["records"]) if category.get("available") else None
        category["read_only"] = True

    generated = utc_now()
    payload = {
        "schema": "jom-users-access-actionable-drilldown-v1",
        "generated_at_utc": iso_utc(generated),
        "status": "ok",
        "source": {
            "organisation_accounts": len(org_by_id),
            "directory_accounts": len(directory_by_id),
            "organisation_pages": org_pages,
            "directory_pages": directory_pages,
            "organisation_pagination_complete": org_complete,
            "directory_pagination_complete": directory_complete,
        },
        "freshness": {"maximum_age_hours": MAXIMUM_AGE_HOURS, "state": "current"},
        "privacy": {"email_stored": False, "raw_responses_stored": False, "account_id_ui_exposure_allowed": False},
        "access": {"phase1_mode": "trusted_local_operator", "future_authorized_role": AUTHORIZED_ROLE, "export_allowed": False, "download_allowed": False, "write_actions_allowed": False},
        "authority": {"safe_to_serve": True, "reason": "Full live organisation and directory pagination succeeded. Unproven Not invited status remains unavailable."},
        "categories": categories,
    }
    write_json_atomic(root / OUTPUT_RELATIVE, payload)
    print(json.dumps({
        "status": "ok",
        "output": str(root / OUTPUT_RELATIVE),
        "organisation_accounts": len(org_by_id),
        "directory_accounts": len(directory_by_id),
        "counts": {key: value_["count"] for key, value_ in categories.items()},
        "not_invited_available": False,
        "email_stored": False,
        "safe_to_serve": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
