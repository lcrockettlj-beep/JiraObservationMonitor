from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from admin_api_client import resolve_org_id, collect_org_users, enrich_users_with_last_active

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RUNTIME_FILE = BASE_DIR / "latest_run.json"
DEFAULT_OUTPUT_FILE = BASE_DIR / "latest_run_admin_enriched.json"
DEFAULT_OUTPUT_PRETTY_FILE = BASE_DIR / "latest_run_admin_enriched_pretty.json"


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Runtime payload not found: {path}")
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Unable to read JSON from {path}: {exc}") from exc
    if not isinstance(content, dict):
        raise RuntimeError(f"Payload at {path} is not a JSON object.")
    return content


def _save_json(path: Path, data: Dict[str, Any], indent: Optional[int] = None) -> None:
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_status(user: Dict[str, Any]) -> str:
    return str(user.get("status") or user.get("accountStatus") or "").strip().lower()


def _row_claim_status(user: Dict[str, Any]) -> str:
    return str(user.get("claimStatus") or "").strip().lower()


def _row_account_type(user: Dict[str, Any]) -> str:
    return str(user.get("accountType") or "").strip().lower()


def _has_org_admin_role(user: Dict[str, Any]) -> bool:
    roles = user.get("platformRoles") or []
    if not isinstance(roles, list):
        return False
    return "atlassian/org-admin" in [str(role).strip().lower() for role in roles]


def _flatten_last_active(user: Dict[str, Any]) -> str:
    payload = _safe_dict(user.get("last_active_dates"))
    rows = _safe_list(payload.get("data"))
    if rows and isinstance(rows[0], dict):
        row = rows[0]
        return str(row.get("lastActive") or row.get("last_active") or row.get("lastActiveDate") or "")
    return ""


def _claim_status_available(users: List[Dict[str, Any]]) -> bool:
    return any(str(u.get("claimStatus", "")).strip() for u in users if isinstance(u, dict))


def _platform_roles_available(users: List[Dict[str, Any]]) -> bool:
    return any(isinstance(u.get("platformRoles"), list) and u.get("platformRoles") for u in users if isinstance(u, dict))


def _mfa_available(users: List[Dict[str, Any]]) -> bool:
    return any("mfaEnabled" in u for u in users if isinstance(u, dict))


def _managed_like_rows(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if _claim_status_available(users):
        return [u for u in users if _row_claim_status(u) == "managed"]
    # Fallback for current row-shape: treat human Atlassian accounts as the best available managed-like population.
    return [u for u in users if _row_account_type(u) == "atlassian"]


def _human_rows(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [u for u in users if _row_account_type(u) == "atlassian"]


def _app_rows(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [u for u in users if _row_account_type(u) == "app"]


def _status_in_userbase_false_rows(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [u for u in users if u.get("statusInUserbase") is False]


def _summary_metrics(users: List[Dict[str, Any]]) -> Dict[str, int]:
    managed_like = _managed_like_rows(users)
    human_rows = _human_rows(users)
    app_rows = _app_rows(users)
    active_rows = [u for u in users if _row_status(u) in {"active", "enabled"}]
    suspended_rows = [u for u in users if _row_status(u) in {"inactive", "suspended", "disabled"}]
    org_admin_rows = [u for u in users if _has_org_admin_role(u)]
    mfa_disabled_rows = [u for u in users if u.get("mfaEnabled") is False]
    return {
        "org_user_count": len(users),
        "managed_user_count": len(managed_like),
        "human_user_count": len(human_rows),
        "app_account_count": len(app_rows),
        "active_user_count": len(active_rows),
        "suspended_user_count": len(suspended_rows),
        "org_admin_count": len(org_admin_rows),
        "mfa_disabled_user_count": len(mfa_disabled_rows),
        "not_in_userbase_count": len(_status_in_userbase_false_rows(users)),
    }


def _table_row(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "accountId": user.get("accountId", ""),
        "accountType": user.get("accountType", ""),
        "claimStatus": user.get("claimStatus", ""),
        "status": user.get("status", ""),
        "accountStatus": user.get("accountStatus", ""),
        "statusInUserbase": user.get("statusInUserbase", ""),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "mfaEnabled": user.get("mfaEnabled", ""),
        "orgAdmin": "Yes" if _has_org_admin_role(user) else "No",
        "lastActive": _flatten_last_active(user),
    }


def _info_row(message: str) -> List[Dict[str, Any]]:
    return [{"note": message}]


def _build_admin_drilldowns(users: List[Dict[str, Any]], summary: Dict[str, int]) -> Dict[str, Any]:
    managed_like_rows = [_table_row(u) for u in _managed_like_rows(users)]
    suspended_rows = [_table_row(u) for u in users if _row_status(u) in {"inactive", "suspended", "disabled"}]
    org_admin_rows = [_table_row(u) for u in users if _has_org_admin_role(u)]
    mfa_disabled_rows = [_table_row(u) for u in users if u.get("mfaEnabled") is False]
    human_rows = [_table_row(u) for u in _human_rows(users)]
    app_rows = [_table_row(u) for u in _app_rows(users)]
    not_in_userbase_rows = [_table_row(u) for u in _status_in_userbase_false_rows(users)]
    summary_rows = [{
        "org_user_count": summary.get("org_user_count", 0),
        "managed_user_count": summary.get("managed_user_count", 0),
        "human_user_count": summary.get("human_user_count", 0),
        "app_account_count": summary.get("app_account_count", 0),
        "active_user_count": summary.get("active_user_count", 0),
        "suspended_user_count": summary.get("suspended_user_count", 0),
        "org_admin_count": summary.get("org_admin_count", 0),
        "mfa_disabled_user_count": summary.get("mfa_disabled_user_count", 0),
        "not_in_userbase_count": summary.get("not_in_userbase_count", 0),
    }]

    managed_reason = (
        "Managed Atlassian accounts returned by the organization user-admin APIs."
        if _claim_status_available(users)
        else "Current admin user rows do not expose claimStatus. This list is the best-available approximation using human Atlassian accounts (accountType=atlassian)."
    )

    org_admin_reason = (
        "Accounts carrying the Atlassian organization admin platform role."
        if _platform_roles_available(users)
        else "Current admin user rows do not expose platformRoles, so organization admin identity is not available in this payload."
    )

    mfa_reason = (
        "Accounts where MFA is reported as disabled by the admin APIs."
        if _mfa_available(users)
        else "Current admin user rows do not expose mfaEnabled, so MFA state is not available in this payload."
    )

    return {
        "admin::summary": {
            "title": "Admin API Enrichment Summary",
            "reason": "Estate-level Atlassian Administration user-management metrics retrieved from the Atlassian admin APIs.",
            "atlassian_area": "Atlassian Administration → Directory / Managed Accounts",
            "columns": ["org_user_count", "managed_user_count", "human_user_count", "app_account_count", "active_user_count", "suspended_user_count", "org_admin_count", "mfa_disabled_user_count", "not_in_userbase_count"],
            "rows": summary_rows,
        },
        "admin::managed_accounts": {
            "title": "Managed / Human Accounts",
            "reason": managed_reason,
            "atlassian_area": "Atlassian Administration → Managed Accounts",
            "columns": ["accountId", "accountType", "claimStatus", "status", "accountStatus", "statusInUserbase", "name", "email", "mfaEnabled", "orgAdmin", "lastActive"],
            "rows": managed_like_rows,
        },
        "admin::human_accounts": {
            "title": "Human Atlassian Accounts",
            "reason": "Human Atlassian user accounts derived from accountType=atlassian in the admin payload.",
            "atlassian_area": "Atlassian Administration → Directory",
            "columns": ["accountId", "accountType", "claimStatus", "status", "accountStatus", "statusInUserbase", "name", "email", "mfaEnabled", "orgAdmin", "lastActive"],
            "rows": human_rows,
        },
        "admin::app_accounts": {
            "title": "App Accounts",
            "reason": "App/service identities derived from accountType=app in the admin payload.",
            "atlassian_area": "Atlassian Administration → Directory",
            "columns": ["accountId", "accountType", "claimStatus", "status", "accountStatus", "statusInUserbase", "name", "email", "mfaEnabled", "orgAdmin", "lastActive"],
            "rows": app_rows,
        },
        "admin::suspended_accounts": {
            "title": "Suspended / Disabled Accounts",
            "reason": "Accounts with suspended, inactive, or disabled accountStatus returned by the admin APIs.",
            "atlassian_area": "Atlassian Administration → Directory / Managed Accounts",
            "columns": ["accountId", "accountType", "claimStatus", "status", "accountStatus", "statusInUserbase", "name", "email", "mfaEnabled", "orgAdmin", "lastActive"],
            "rows": suspended_rows,
        },
        "admin::org_admins": {
            "title": "Organization Admins",
            "reason": org_admin_reason,
            "atlassian_area": "Atlassian Administration → Organization settings",
            "columns": ["accountId", "accountType", "claimStatus", "status", "accountStatus", "statusInUserbase", "name", "email", "mfaEnabled", "orgAdmin", "lastActive"] if org_admin_rows else ["note"],
            "rows": org_admin_rows if org_admin_rows else _info_row(org_admin_reason),
        },
        "admin::mfa_disabled": {
            "title": "MFA Disabled Accounts",
            "reason": mfa_reason,
            "atlassian_area": "Atlassian Administration → Security / Authentication policies",
            "columns": ["accountId", "accountType", "claimStatus", "status", "accountStatus", "statusInUserbase", "name", "email", "mfaEnabled", "orgAdmin", "lastActive"] if mfa_disabled_rows else ["note"],
            "rows": mfa_disabled_rows if mfa_disabled_rows else _info_row(mfa_reason),
        },
        "admin::not_in_userbase": {
            "title": "Accounts Not In Userbase",
            "reason": "Accounts where statusInUserbase is false in the admin payload.",
            "atlassian_area": "Atlassian Administration → Directory",
            "columns": ["accountId", "accountType", "claimStatus", "status", "accountStatus", "statusInUserbase", "name", "email", "mfaEnabled", "orgAdmin", "lastActive"],
            "rows": not_in_userbase_rows,
        },
    }


def enrich_runtime_payload(runtime_path: Path, output_path: Path, output_pretty_path: Path, include_last_active: bool = False, last_active_max_users: int = 25) -> Dict[str, Any]:
    payload = _load_json(runtime_path)
    org_id = resolve_org_id()
    users, collection_meta = collect_org_users(org_id=org_id, limit=100, max_pages=100, sleep_seconds=0.0)
    if include_last_active and last_active_max_users > 0:
        users = enrich_users_with_last_active(org_id=org_id, users=users, max_users=last_active_max_users, sleep_seconds=0.1)

    summary = _summary_metrics(users)
    admin_enrichment = {
        "collected_at_utc": _iso_now(),
        "org_id": org_id,
        "collection_meta": collection_meta,
        "summary": summary,
        "users": users,
        "last_active_enabled": bool(include_last_active),
        "last_active_user_cap": int(last_active_max_users),
    }

    estate = _safe_dict(payload.get("estate"))
    estate.update({
        "total_users": summary.get("org_user_count"),
        "total_active_users": summary.get("active_user_count"),
        "managed_disabled_accounts": summary.get("suspended_user_count"),
        "org_admin_count": summary.get("org_admin_count"),
        "mfa_disabled_accounts": summary.get("mfa_disabled_user_count"),
        "managed_user_count": summary.get("managed_user_count"),
        "human_user_count": summary.get("human_user_count"),
        "app_account_count": summary.get("app_account_count"),
        "not_in_userbase_count": summary.get("not_in_userbase_count"),
    })
    payload["estate"] = estate
    payload["admin_enrichment"] = admin_enrichment

    drilldowns = _safe_dict(payload.get("drilldowns"))
    drilldowns.update(_build_admin_drilldowns(users, summary))
    payload["drilldowns"] = drilldowns

    _save_json(output_path, payload, indent=None)
    _save_json(output_pretty_path, payload, indent=2)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich latest_run.json with Atlassian Admin API data using current admin row-shape.")
    parser.add_argument("--runtime-file", default=str(DEFAULT_RUNTIME_FILE))
    parser.add_argument("--output-file", default=str(DEFAULT_OUTPUT_FILE))
    parser.add_argument("--output-pretty-file", default=str(DEFAULT_OUTPUT_PRETTY_FILE))
    parser.add_argument("--include-last-active", action="store_true")
    parser.add_argument("--last-active-max-users", type=int, default=25)
    args = parser.parse_args()
    try:
        payload = enrich_runtime_payload(
            runtime_path=Path(args.runtime_file),
            output_path=Path(args.output_file),
            output_pretty_path=Path(args.output_pretty_file),
            include_last_active=bool(args.include_last_active),
            last_active_max_users=max(0, int(args.last_active_max_users)),
        )
        summary = _safe_dict(_safe_dict(payload.get("admin_enrichment")).get("summary"))
        print("Admin row-shape enrichment patch complete.")
        print(f"Org users: {summary.get('org_user_count', 0)}")
        print(f"Managed-like users: {summary.get('managed_user_count', 0)}")
        print(f"Human users: {summary.get('human_user_count', 0)}")
        print(f"App accounts: {summary.get('app_account_count', 0)}")
        print(f"Suspended users: {summary.get('suspended_user_count', 0)}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
