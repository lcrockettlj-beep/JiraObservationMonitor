# JOM Verified Active Jira Users authority builder v1
# Approved policy: jira-software only, 30-day window, 26-hour maximum age,
# unavailable unless every authoritative account request succeeds.
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API_HOST = "https://api.atlassian.com/admin"
DIRECTORY_AUTHORITY = Path("runtime/data/admin_directory_users.json")
PRODUCT_AUTHORITY = Path("runtime/data/estate_product_access.json")
OUTPUT_RELATIVE = Path("runtime/data/verified_active_jira_users_v1.json")
PRODUCT_KEY = "jira-software"
ACTIVITY_WINDOW_DAYS = 30
MAXIMUM_AGE_HOURS = 26
MIN_REQUEST_DELAY_SECONDS = 0.31
DEFAULT_REQUEST_DELAY_SECONDS = 0.35


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def load_json(path: Path) -> Tuple[Dict[str, Any], Optional[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return {}, "root payload is not an object"
        return value, None
    except FileNotFoundError:
        return {}, "missing"
    except Exception as exc:
        return {}, f"invalid: {type(exc).__name__}: {str(exc)[:200]}"


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def request_json(url: str, token: str) -> Tuple[int, Any]:
    request = urllib.request.Request(
        url=url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception:
        return 0, {}


def parse_timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def product_rows(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("product_access")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def product_authority_proves_jira(payload: Dict[str, Any]) -> bool:
    return PRODUCT_KEY in json.dumps(payload, ensure_ascii=False).lower()


def unavailable_payload(generated: datetime, reason: str, authoritative_accounts: int = 0) -> Dict[str, Any]:
    return {
        "schema": "jom-verified-active-jira-users-v1",
        "generated_at_utc": iso_utc(generated),
        "status": "unavailable",
        "scope": {"product_key": PRODUCT_KEY, "activity_window_days": ACTIVITY_WINDOW_DAYS},
        "source": {
            "authority": "Atlassian Admin Organizations API last-active-dates",
            "authoritative_accounts": authoritative_accounts,
            "successful_requests": 0,
            "failed_requests": authoritative_accounts,
        },
        "summary": {
            "verified_active_jira_users": None,
            "accounts_with_jira_product_rows": None,
            "accounts_without_jira_product_rows": None,
        },
        "quality": {"timestamp_parse_failures": None, "future_timestamps": None, "full_success": False},
        "freshness": {"maximum_age_hours": MAXIMUM_AGE_HOURS, "state": "current"},
        "authority": {"safe_to_publish": False, "reason": reason},
        "privacy": {"aggregate_only": True, "account_ids_stored": False, "raw_responses_stored": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Verified Active Jira Users live authority.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--delay", type=float, default=DEFAULT_REQUEST_DELAY_SECONDS)
    args = parser.parse_args()
    if args.delay < MIN_REQUEST_DELAY_SECONDS:
        raise SystemExit(f"--delay must be at least {MIN_REQUEST_DELAY_SECONDS:.2f} seconds")

    root = Path(args.project_root).resolve()
    output = root / OUTPUT_RELATIVE
    generated = utc_now()
    directory, directory_error = load_json(root / DIRECTORY_AUTHORITY)
    product_authority, product_error = load_json(root / PRODUCT_AUTHORITY)

    if directory_error:
        payload = unavailable_payload(generated, f"Directory authority {directory_error}.")
        write_json(output, payload)
        print(json.dumps({"status": payload["status"], "output": str(output), "reason": payload["authority"]["reason"]}, indent=2))
        return 2

    users = directory.get("users") if isinstance(directory.get("users"), list) else []
    account_ids = sorted({
        str(row.get("account_id", "")).strip()
        for row in users
        if isinstance(row, dict) and str(row.get("account_id", "")).strip()
    })
    if not account_ids:
        payload = unavailable_payload(generated, "Directory authority contains no authoritative account IDs.")
        write_json(output, payload)
        print(json.dumps({"status": payload["status"], "output": str(output), "reason": payload["authority"]["reason"]}, indent=2))
        return 2

    if product_error or not product_authority_proves_jira(product_authority):
        reason = "Jira Software product authority is missing or does not prove jira-software."
        payload = unavailable_payload(generated, reason, len(account_ids))
        write_json(output, payload)
        print(json.dumps({"status": payload["status"], "output": str(output), "reason": reason}, indent=2))
        return 2

    env = load_env(root)
    org_id = env.get("ATLASSIAN_ADMIN_ORG_ID", "").strip()
    token = env.get("ATLASSIAN_ADMIN_API_KEY", "").strip()
    if not org_id or not token:
        payload = unavailable_payload(generated, "Missing ATLASSIAN_ADMIN_ORG_ID or ATLASSIAN_ADMIN_API_KEY.", len(account_ids))
        write_json(output, payload)
        print(json.dumps({"status": payload["status"], "output": str(output), "reason": payload["authority"]["reason"]}, indent=2))
        return 2

    successful_requests = 0
    failed_requests = 0
    accounts_with_jira_rows = 0
    accounts_without_jira_rows = 0
    timestamp_parse_failures = 0
    future_timestamps = 0
    latest_by_account: Dict[str, datetime] = {}

    for index, account_id in enumerate(account_ids):
        url = (
            f"{API_HOST}/v1/orgs/{urllib.parse.quote(org_id, safe='')}"
            f"/directory/users/{urllib.parse.quote(account_id, safe='')}/last-active-dates"
        )
        status, response = request_json(url, token)
        if status != 200:
            failed_requests += 1
        else:
            successful_requests += 1
            matching_rows = [
                row for row in product_rows(response)
                if str(row.get("key") or "").strip().lower() == PRODUCT_KEY
            ]
            if matching_rows:
                accounts_with_jira_rows += 1
            else:
                accounts_without_jira_rows += 1
            valid: List[datetime] = []
            for row in matching_rows:
                raw_timestamp = row.get("last_active_timestamp")
                parsed = parse_timestamp(raw_timestamp)
                if parsed is None and raw_timestamp not in (None, ""):
                    timestamp_parse_failures += 1
                if parsed is not None:
                    if parsed > generated:
                        future_timestamps += 1
                    valid.append(parsed)
            if valid:
                latest_by_account[account_id] = max(valid)
        if index < len(account_ids) - 1:
            time.sleep(args.delay)

    full_success = successful_requests == len(account_ids) and failed_requests == 0
    quality_passed = timestamp_parse_failures == 0 and future_timestamps == 0
    active_count = sum(
        1 for timestamp in latest_by_account.values()
        if 0 <= (generated - timestamp).total_seconds() <= ACTIVITY_WINDOW_DAYS * 86400
    )
    safe_to_publish = bool(full_success and quality_passed)
    if not full_success:
        reason = "Unavailable because not every authoritative account request succeeded."
    elif not quality_passed:
        reason = "Unavailable because timestamp quality gates failed."
    else:
        reason = "Live Jira Software activity authority passed all approved publish gates."

    payload = {
        "schema": "jom-verified-active-jira-users-v1",
        "generated_at_utc": iso_utc(generated),
        "status": "ok" if safe_to_publish else "unavailable",
        "scope": {"product_key": PRODUCT_KEY, "activity_window_days": ACTIVITY_WINDOW_DAYS},
        "source": {
            "authority": "Atlassian Admin Organizations API last-active-dates",
            "authoritative_accounts": len(account_ids),
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
        },
        "summary": {
            "verified_active_jira_users": active_count if safe_to_publish else None,
            "accounts_with_jira_product_rows": accounts_with_jira_rows if full_success else None,
            "accounts_without_jira_product_rows": accounts_without_jira_rows if full_success else None,
        },
        "quality": {
            "timestamp_parse_failures": timestamp_parse_failures,
            "future_timestamps": future_timestamps,
            "full_success": full_success,
        },
        "freshness": {"maximum_age_hours": MAXIMUM_AGE_HOURS, "state": "current"},
        "authority": {"safe_to_publish": safe_to_publish, "reason": reason},
        "privacy": {"aggregate_only": True, "account_ids_stored": False, "raw_responses_stored": False},
    }
    write_json(output, payload)
    print(json.dumps({
        "status": payload["status"],
        "output": str(output),
        "scope": PRODUCT_KEY,
        "activity_window_days": ACTIVITY_WINDOW_DAYS,
        "authoritative_accounts": len(account_ids),
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "verified_active_jira_users": payload["summary"]["verified_active_jira_users"],
        "safe_to_publish": safe_to_publish,
    }, indent=2))
    return 0 if safe_to_publish else 2


if __name__ == "__main__":
    raise SystemExit(main())
