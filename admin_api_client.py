from __future__ import annotations
import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from auth import get_admin_headers, get_admin_org_id, get_admin_orgs

ADMIN_BASE = "https://api.atlassian.com"
ORGS_BASE = f"{ADMIN_BASE}/admin/v1"


def _http_json(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, payload: Optional[Dict[str, Any]] = None) -> Any:
    headers = headers or {}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} calling {url}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc


def resolve_org_id() -> str:
    configured = get_admin_org_id(required=False)
    if configured:
        return configured
    orgs = get_admin_orgs()
    if not orgs:
        raise RuntimeError("No Atlassian admin organizations returned. Set ATLASSIAN_ADMIN_ORG_ID in .env or verify your admin API key.")
    first = orgs[0]
    org_id = str(first.get("id", "")).strip()
    if not org_id:
        raise RuntimeError("Unable to resolve an Atlassian admin organization ID from the org list.")
    return org_id


def get_orgs() -> List[Dict[str, Any]]:
    response = _http_json(f"{ORGS_BASE}/orgs", headers=get_admin_headers())
    data = response.get("data") if isinstance(response, dict) else None
    if isinstance(data, list):
        return data
    if isinstance(response, list):
        return response
    return []


def search_users(org_id: str, cursor: Optional[str] = None, limit: int = 100, claim_status: Optional[str] = None, account_status: Optional[List[str]] = None, status: Optional[List[str]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"limit": int(limit)}
    if cursor:
        payload["cursor"] = cursor
    if claim_status:
        payload["claimStatus"] = claim_status
    if account_status:
        payload["accountStatus"] = account_status
    if status:
        payload["status"] = status
    url = f"{ORGS_BASE}/orgs/{urllib.parse.quote(org_id)}/users/search"
    return _http_json(url, method="POST", headers=get_admin_headers(), payload=payload)


def collect_org_users(org_id: str, limit: int = 100, max_pages: int = 100, sleep_seconds: float = 0.0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    pages = 0

    while pages < max_pages:
        page = search_users(org_id=org_id, cursor=cursor, limit=limit)
        rows = page.get("data") if isinstance(page, dict) else None
        if not isinstance(rows, list):
            rows = []
        all_rows.extend([row for row in rows if isinstance(row, dict)])
        pages += 1

        next_cursor = None
        links = page.get("links", {}) if isinstance(page, dict) else {}
        next_link = str(links.get("next", "")).strip()
        if next_link:
            try:
                parsed = urllib.parse.urlparse(next_link)
                params = urllib.parse.parse_qs(parsed.query)
                next_cursor = (params.get("cursor") or [None])[0]
            except Exception:
                next_cursor = None
        if not next_cursor:
            break
        cursor = next_cursor
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    meta = {
        "pages_collected": pages,
        "rows_collected": len(all_rows),
        "limit": int(limit),
        "max_pages": int(max_pages),
    }
    return all_rows, meta


def get_last_active_dates(org_id: str, account_id: str) -> Dict[str, Any]:
    url = f"{ORGS_BASE}/orgs/{urllib.parse.quote(org_id)}/directory/users/{urllib.parse.quote(account_id)}/last-active-dates"
    response = _http_json(url, headers=get_admin_headers())
    return response if isinstance(response, dict) else {}


def enrich_users_with_last_active(org_id: str, users: List[Dict[str, Any]], max_users: int = 25, sleep_seconds: float = 0.1) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for index, user in enumerate(users):
        row = dict(user)
        if index < max_users:
            account_id = str(user.get("accountId", "")).strip()
            if account_id:
                try:
                    row["last_active_dates"] = get_last_active_dates(org_id, account_id)
                except Exception as exc:
                    row["last_active_dates_error"] = str(exc)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
        enriched.append(row)
    return enriched
