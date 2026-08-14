# JOM Named User Display Identity authority builder v1
# Approved contract: display name only, account ID as internal reconciliation key,
# email and raw responses discarded, 26-hour maximum age, atomic full-success replacement.
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

API_HOST = "https://api.atlassian.com/admin"
DIRECTORY_AUTHORITY = Path("runtime/data/admin_directory_users.json")
USER_FOOTPRINT = Path("runtime/data/user_footprint.json")
NAMED_SITE_ACCESS = Path("runtime/data/named_site_access_authority_v1.json")
OUTPUT_RELATIVE = Path("runtime/data/named_user_display_identity_v1.json")
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


def load_json(path: Path) -> Tuple[Any, Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return {}, "missing"
    except Exception as exc:
        return {}, f"invalid: {type(exc).__name__}: {str(exc)[:160]}"


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
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
        exc.read()
        return exc.code, {}
    except Exception:
        return 0, {}


def extract_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "values", "users", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
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


def get_all(url: str, token: str, max_pages: int = 1000) -> Tuple[List[Dict[str, Any]], int, bool, Counter]:
    collected: List[Dict[str, Any]] = []
    seen = set()
    statuses: Counter = Counter()
    current = url
    pages = 0
    while current:
        if current in seen:
            raise RuntimeError("Pagination loop detected")
        if pages >= max_pages:
            raise RuntimeError("Pagination safety limit exceeded")
        seen.add(current)
        status, payload = request_json(current, token)
        statuses[status] += 1
        pages += 1
        if status != 200:
            return collected, pages, False, statuses
        collected.extend(extract_rows(payload))
        current = next_url(payload, current)
    return collected, pages, True, statuses


def account_id(row: Dict[str, Any]) -> str:
    return str(row.get("accountId") or row.get("account_id") or row.get("id") or row.get("userId") or "").strip()


def display_name(row: Dict[str, Any]) -> str:
    return str(row.get("displayName") or row.get("display_name") or row.get("name") or "").strip()


def account_status(row: Dict[str, Any]) -> str:
    return str(row.get("accountStatus") or row.get("account_status") or row.get("status") or "unknown").strip().lower()


def footprint_mapping(footprint: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    output: Dict[str, Dict[str, Any]] = {}
    users = footprint.get("users") if isinstance(footprint.get("users"), list) else []
    for row in users:
        if not isinstance(row, dict):
            continue
        key = account_id(row)
        if not key:
            continue
        sites = sorted({str(value).strip() for value in (row.get("sites") or []) if str(value).strip()})
        output[key] = {
            "sites": sites,
            "site_count": len(sites),
            "product_access_assignments": int(row.get("product_access_assignments") or 0),
        }
    return output


def unavailable(reason: str, generated: datetime, authoritative_accounts: int = 0, named_accounts: int = 0) -> Dict[str, Any]:
    return {
        "schema": "jom-named-user-display-identity-v1",
        "generated_at_utc": iso_utc(generated),
        "status": "unavailable",
        "source": {
            "authoritative_accounts": authoritative_accounts,
            "named_access_accounts": named_accounts,
            "matched_accounts": 0,
            "unmatched_accounts": named_accounts,
        },
        "quality": {
            "pagination_complete": False,
            "display_name_coverage_complete": False,
            "email_stored": False,
            "raw_responses_stored": False,
        },
        "freshness": {"maximum_age_hours": MAXIMUM_AGE_HOURS, "state": "current"},
        "access": {
            "authorized_role": AUTHORIZED_ROLE,
            "deny_by_default": True,
            "export_allowed": False,
            "bulk_copy_allowed": False,
            "access_logging_required": True,
        },
        "authority": {"safe_to_serve": False, "reason": reason},
        "users": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Named User Display Identity runtime authority.")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    if not (root / "app").exists() or not (root / "runtime" / "data").exists():
        raise SystemExit("Run from the JiraObservationMonitor repository root.")

    generated = utc_now()
    output = root / OUTPUT_RELATIVE
    directory, directory_error = load_json(root / DIRECTORY_AUTHORITY)
    footprint, footprint_error = load_json(root / USER_FOOTPRINT)
    named_access, named_error = load_json(root / NAMED_SITE_ACCESS)
    if directory_error or footprint_error or named_error:
        payload = unavailable(
            f"Required authority unavailable: directory={directory_error}, footprint={footprint_error}, named_site_access={named_error}",
            generated,
        )
        print(json.dumps({"status": payload["status"], "output_unchanged": True, "reason": payload["authority"]["reason"]}, indent=2))
        return 2

    directory_users = directory.get("users") if isinstance(directory, dict) and isinstance(directory.get("users"), list) else []
    authoritative_ids = {account_id(row) for row in directory_users if isinstance(row, dict) and account_id(row)}
    directory_ids = sorted({str(row.get("directory_id", "")).strip() for row in directory_users if isinstance(row, dict) and str(row.get("directory_id", "")).strip()})
    mapping = footprint_mapping(footprint if isinstance(footprint, dict) else {})
    named_ids = set(mapping)
    named_capabilities = named_access.get("capabilities") if isinstance(named_access, dict) and isinstance(named_access.get("capabilities"), dict) else {}
    named_access_live = isinstance(named_access, dict) and named_access.get("status") == "live"
    aggregate_mapping_live = named_capabilities.get("aggregate_site_user_counts") is True

    if not authoritative_ids or not directory_ids or not named_ids or not named_access_live or not aggregate_mapping_live:
        reason = "Directory or named-access authority is incomplete or not live. Existing runtime authority was preserved."
        print(json.dumps({"status": "unavailable", "output_unchanged": True, "reason": reason}, indent=2))
        return 2

    env = load_env(root)
    org_id = env.get("ATLASSIAN_ADMIN_ORG_ID", "").strip()
    token = env.get("ATLASSIAN_ADMIN_API_KEY", "").strip()
    if not org_id or not token:
        reason = "Missing ATLASSIAN_ADMIN_ORG_ID or ATLASSIAN_ADMIN_API_KEY. Existing runtime authority was preserved."
        print(json.dumps({"status": "unavailable", "output_unchanged": True, "reason": reason}, indent=2))
        return 2

    live_rows: List[Dict[str, Any]] = []
    pages = 0
    pagination_complete = True
    statuses: Counter = Counter()
    for directory_id in directory_ids:
        url = f"{API_HOST}/v2/orgs/{urllib.parse.quote(org_id, safe='')}/directories/{urllib.parse.quote(directory_id, safe='')}/users?limit=100"
        collected, page_count, complete, directory_statuses = get_all(url, token)
        live_rows.extend(collected)
        pages += page_count
        pagination_complete = pagination_complete and complete
        statuses.update(directory_statuses)

    live_by_id = {account_id(row): row for row in live_rows if account_id(row)}
    live_ids = set(live_by_id)
    matched_ids = named_ids & live_ids
    unmatched_ids = named_ids - live_ids
    complete_directory = pagination_complete and authoritative_ids == (authoritative_ids & live_ids) and len(live_ids) == len(authoritative_ids)

    output_users = []
    missing_display_names = 0
    for key in sorted(matched_ids):
        source_row = live_by_id[key]
        label = display_name(source_row)
        if not label:
            missing_display_names += 1
            continue
        mapped = mapping[key]
        output_users.append({
            "account_id": key,
            "display_name": label,
            "account_status": account_status(source_row),
            "sites": mapped["sites"],
            "site_count": mapped["site_count"],
            "product_access_assignments": mapped["product_access_assignments"],
        })

    full_success = bool(
        set(statuses) == {200}
        and complete_directory
        and not unmatched_ids
        and missing_display_names == 0
        and len(output_users) == len(named_ids)
    )
    if not full_success:
        reason = "Full Directory, named-access, or display-name coverage failed. Existing runtime authority was preserved."
        print(json.dumps({
            "status": "unavailable",
            "output_unchanged": True,
            "authoritative_accounts": len(authoritative_ids),
            "named_access_accounts": len(named_ids),
            "matched_accounts": len(matched_ids),
            "unmatched_accounts": len(unmatched_ids),
            "missing_display_names": missing_display_names,
            "reason": reason,
        }, indent=2))
        return 2

    output_users.sort(key=lambda row: (row["display_name"].casefold(), row["account_id"]))
    payload = {
        "schema": "jom-named-user-display-identity-v1",
        "generated_at_utc": iso_utc(generated),
        "status": "ok",
        "source": {
            "authority": "Atlassian Admin Directory users plus JOM named-access authority",
            "authoritative_accounts": len(authoritative_ids),
            "named_access_accounts": len(named_ids),
            "matched_accounts": len(output_users),
            "unmatched_accounts": 0,
            "directory_pages": pages,
        },
        "quality": {
            "pagination_complete": True,
            "display_name_coverage_complete": True,
            "email_stored": False,
            "raw_responses_stored": False,
            "synthetic_labels_created": False,
        },
        "freshness": {"maximum_age_hours": MAXIMUM_AGE_HOURS, "state": "current"},
        "retention": {"mode": "current_authority_only", "atomic_replacement": True},
        "access": {
            "authorized_role": AUTHORIZED_ROLE,
            "deny_by_default": True,
            "server_endpoint_only": True,
            "access_logging_required": True,
            "export_allowed": False,
            "download_allowed": False,
            "bulk_copy_allowed": False,
            "email_exposure_allowed": False,
        },
        "authority": {
            "safe_to_serve": True,
            "reason": "Full live Directory identity coverage and named-access reconciliation passed all approved builder gates.",
        },
        "users": output_users,
    }
    write_json_atomic(output, payload)
    print(json.dumps({
        "status": "ok",
        "output": str(output),
        "authoritative_accounts": len(authoritative_ids),
        "named_access_accounts": len(named_ids),
        "matched_accounts": len(output_users),
        "unmatched_accounts": 0,
        "display_name_coverage_complete": True,
        "email_stored": False,
        "authorized_role": AUTHORIZED_ROLE,
        "safe_to_serve": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
