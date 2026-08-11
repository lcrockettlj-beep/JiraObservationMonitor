# JOM Admin Directory Users safe paginated collector v1
# Collects privacy-minimised Atlassian directory authority without raw responses,
# names, email addresses, avatars, tokens, or authorization headers.
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

API_HOST = "https://api.atlassian.com/admin"
OUTPUT_RELATIVE = Path("runtime/data/admin_directory_users.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_env(root: Path) -> Dict[str, str]:
    env = dict(os.environ)
    path = root / ".env"
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def request_json(method: str, url: str, token: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"Atlassian endpoint returned HTTP {exc.code}: {detail}") from exc


def data_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "values", "users", "directories"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def next_url(payload: Any, current_url: str) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
    value = links.get("next") or payload.get("next") or payload.get("nextPage")
    if isinstance(value, str) and value.strip():
        next_value = value.strip()
        if next_value.startswith(("http://", "https://", "/", "?")):
            return urllib.parse.urljoin(current_url, next_value)
        parsed = urllib.parse.urlsplit(current_url)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        query["cursor"] = [next_value]
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


def get_all(url: str, token: str, max_pages: int = 1000) -> Tuple[List[Dict[str, Any]], int, bool]:
    rows: List[Dict[str, Any]] = []
    seen_urls = set()
    page_count = 0
    current = url
    while current:
        if current in seen_urls:
            raise RuntimeError("Pagination loop detected")
        if page_count >= max_pages:
            raise RuntimeError(f"Pagination exceeded safety limit of {max_pages} pages")
        seen_urls.add(current)
        status, payload = request_json("GET", current, token)
        if status != 200:
            raise RuntimeError(f"Unexpected HTTP {status}")
        rows.extend(data_rows(payload))
        page_count += 1
        current = next_url(payload, current)
    return rows, page_count, True


def value(row: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def norm(value_in: Any) -> str:
    return str(value_in or "").strip().lower().replace("-", "_").replace(" ", "_")


def bool_value(value_in: Any) -> Optional[bool]:
    if isinstance(value_in, bool):
        return value_in
    text = norm(value_in)
    if text in {"true", "yes", "1", "enabled"}:
        return True
    if text in {"false", "no", "0", "disabled"}:
        return False
    return None


def list_strings(value_in: Any) -> List[str]:
    if not isinstance(value_in, list):
        return []
    result = []
    for item in value_in:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            candidate = value(item, "id", "key", "name", "roleId", "resourceId", "productId")
            if candidate:
                result.append(str(candidate))
    return sorted(set(result))


def product_access_count(row: Dict[str, Any]) -> int:
    access = value(row, "productAccess", "product_access")
    if isinstance(access, list):
        return len(access)
    if isinstance(access, dict):
        return len(access)
    counts = row.get("counts") if isinstance(row.get("counts"), dict) else {}
    candidate = counts.get("resources") or counts.get("productAccess")
    try:
        return int(candidate) if candidate is not None else 0
    except (TypeError, ValueError):
        return 0


def minimise_user(row: Dict[str, Any], directory_id: str) -> Optional[Dict[str, Any]]:
    account_id = value(row, "accountId", "account_id", "userId", "user_id", "id")
    if not account_id:
        return None
    platform_roles = list_strings(value(row, "platformRoles", "platform_roles"))
    group_ids = list_strings(value(row, "groups", "groupIds", "group_ids"))
    return {
        "account_id": str(account_id),
        "directory_id": directory_id,
        "account_type": norm(value(row, "accountType", "account_type")) or "unknown",
        "account_status": norm(value(row, "accountStatus", "account_status", "status")) or "unknown",
        "membership_status": norm(value(row, "membershipStatus", "membership_status")) or "unknown",
        "claim_status": norm(value(row, "claimStatus", "claim_status")) or "unknown",
        "management_source": norm(value(row, "managementSource", "management_source", "managedBy")) or "unknown",
        "mfa_enabled": bool_value(value(row, "mfaEnabled", "mfa_enabled")),
        "email_verified": bool_value(value(row, "emailVerified", "email_verified")),
        "platform_roles": platform_roles,
        "group_ids": group_ids,
        "product_access_count": product_access_count(row),
    }


def count_values(users: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    counts = Counter(str(user.get(key, "unknown")) for user in users)
    return dict(sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect privacy-safe, fully paginated Atlassian directory user authority.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--sample-users", type=int, default=0, help="Compatibility option retained; full pagination is always used.")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    env = load_env(root)
    org_id = env.get("ATLASSIAN_ADMIN_ORG_ID", "").strip()
    token = env.get("ATLASSIAN_ADMIN_API_KEY", "").strip()
    if not org_id or not token:
        raise SystemExit("Missing ATLASSIAN_ADMIN_ORG_ID or ATLASSIAN_ADMIN_API_KEY")

    output = root / OUTPUT_RELATIVE
    generated = utc_now()
    errors: List[Dict[str, Any]] = []
    directories: List[Dict[str, Any]] = []
    users_by_id: Dict[str, Dict[str, Any]] = {}
    total_pages = 0
    complete = True

    directory_url = f"{API_HOST}/v2/orgs/{urllib.parse.quote(org_id)}/directories?limit=100"
    directory_rows, pages, directory_complete = get_all(directory_url, token)
    total_pages += pages
    complete = complete and directory_complete

    for directory in directory_rows:
        directory_id = value(directory, "id", "directoryId", "directory_id")
        if not directory_id:
            continue
        directory_id = str(directory_id)
        users_url = f"{API_HOST}/v2/orgs/{urllib.parse.quote(org_id)}/directories/{urllib.parse.quote(directory_id)}/users?limit=100"
        try:
            rows, pages, users_complete = get_all(users_url, token)
            total_pages += pages
            complete = complete and users_complete
            retained = 0
            for row in rows:
                user = minimise_user(row, directory_id)
                if not user:
                    continue
                existing = users_by_id.get(user["account_id"])
                if existing is None:
                    users_by_id[user["account_id"]] = user
                else:
                    existing["platform_roles"] = sorted(set(existing["platform_roles"] + user["platform_roles"]))
                    existing["group_ids"] = sorted(set(existing["group_ids"] + user["group_ids"]))
                    existing["product_access_count"] = max(existing["product_access_count"], user["product_access_count"])
                retained += 1
            directories.append({"directory_id": directory_id, "pages": pages, "rows_received": len(rows), "rows_retained": retained, "complete": users_complete})
        except Exception as exc:
            complete = False
            errors.append({"directory_id": directory_id, "stage": "directory_users", "error": str(exc)[:500]})

    users = sorted(users_by_id.values(), key=lambda item: item["account_id"])
    account_types = count_values(users, "account_type")
    account_statuses = count_values(users, "account_status")
    membership_statuses = count_values(users, "membership_status")
    claim_statuses = count_values(users, "claim_status")
    management_sources = count_values(users, "management_source")
    mfa_enabled = sum(1 for user in users if user.get("mfa_enabled") is True)
    mfa_disabled = sum(1 for user in users if user.get("mfa_enabled") is False)
    mfa_unknown = len(users) - mfa_enabled - mfa_disabled
    email_verified = sum(1 for user in users if user.get("email_verified") is True)
    email_unverified = sum(1 for user in users if user.get("email_verified") is False)
    email_verification_unknown = len(users) - email_verified - email_unverified
    platform_role_assignments = sum(len(user.get("platform_roles", [])) for user in users)
    product_access_assignments = sum(int(user.get("product_access_count", 0)) for user in users)

    payload: Dict[str, Any] = {
        "schema": "jom-admin-directory-users-authority-v1",
        "generated_at_utc": generated,
        "status": "ok" if complete and not errors else "attention",
        "source": {
            "authority": "Atlassian Admin Organizations API",
            "endpoint_templates": [
                "/admin/v2/orgs/{orgId}/directories",
                "/admin/v2/orgs/{orgId}/directories/{directoryId}/users",
            ],
            "live_collection": True,
            "pagination_complete": complete,
            "page_count": total_pages,
            "directory_count": len(directories),
            "credential_present": True,
        },
        "privacy": {
            "raw_responses_stored": False,
            "names_stored": False,
            "emails_stored": False,
            "avatars_stored": False,
            "account_ids_stored": True,
            "account_id_reason": "Required as the stable Atlassian identity key for reconciliation and drill-down authority.",
        },
        "summary": {
            "unique_accounts": len(users),
            "account_types": account_types,
            "account_statuses": account_statuses,
            "membership_statuses": membership_statuses,
            "claim_statuses": claim_statuses,
            "management_sources": management_sources,
            "mfa_enabled": mfa_enabled,
            "mfa_disabled": mfa_disabled,
            "mfa_unknown": mfa_unknown,
            "email_verified": email_verified,
            "email_unverified": email_unverified,
            "email_verification_unknown": email_verification_unknown,
            "platform_role_assignments": platform_role_assignments,
            "product_access_assignments": product_access_assignments,
            "active_users": None,
            "active_users_reason": "Account status does not prove user activity. Last-active authority is not collected by this contract.",
        },
        "directories": directories,
        "users": users,
        "errors": errors,
        "safe_to_use_for_account_authority": bool(complete and users),
        "safe_to_use_for_active_user_authority": False,
    }
    write_json(output, payload)
    print("Admin Directory users authority collected.")
    print(json.dumps({
        "output": str(output),
        "status": payload["status"],
        "pagination_complete": complete,
        "directory_count": len(directories),
        "unique_accounts": len(users),
        "errors": len(errors),
    }, indent=2))
    return 0 if complete and users else 2


if __name__ == "__main__":
    raise SystemExit(main())
