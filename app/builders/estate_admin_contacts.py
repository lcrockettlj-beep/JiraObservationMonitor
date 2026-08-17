from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_ADMIN_HOST = "https://api.atlassian.com/admin"
ROOT = Path(__file__).resolve().parents[2]
CONTACTS_OUT = ROOT / "runtime" / "data" / "estate_admin_contacts_v1.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_env(root: Path | None = None) -> dict[str, str]:
    root = root or ROOT
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


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def request_json(method: str, url: str, token: str, body: Any = None) -> tuple[bool, int, Any, str | None]:
    data = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw) if raw else {}
            return True, int(response.status), payload, None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")[:700]
        return False, int(exc.code), None, raw
    except Exception as exc:
        return False, 0, None, str(exc)[:700]


def extract_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ["data", "values", "directories", "workspaces", "users", "groups", "items"]:
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def extract_ids(rows: list[dict[str, Any]], names: list[str]) -> list[str]:
    out: list[str] = []
    for row in rows:
        for name in names:
            value = row.get(name)
            if value and str(value) not in out:
                out.append(str(value))
    return out


def site_records(root: Path = ROOT) -> list[dict[str, Any]]:
    paths = [
        root / "runtime" / "data" / "estate_discovery_authority_v1.json",
        root / "runtime" / "data" / "estate_admin_site_inventory_v1.json",
        root / "runtime" / "data" / "site_registry.json",
    ]
    sites: list[dict[str, Any]] = []
    seen = set()
    for path in paths:
        payload = read_json(path, {}) or {}
        for site in payload.get("sites", []) if isinstance(payload, dict) else []:
            if not isinstance(site, dict):
                continue
            key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url") or site.get("name")
            if not key or str(key) in seen:
                continue
            seen.add(str(key))
            sites.append({
                "site_key": str(key),
                "name": site.get("name") or site.get("site_name") or str(key),
                "url": site.get("url") or site.get("site_url"),
                "cloud_id": site.get("cloud_id") or site.get("cloudId") or site.get("id") or site.get("site_id") or site.get("resource_id"),
                "raw": site,
            })
    return sites


def sample_account_ids(root: Path = ROOT, limit: int = 20) -> list[str]:
    candidates = [
        root / "runtime" / "data" / "admin_truth_v2.json",
        root / "runtime" / "data" / "user_footprint.json",
        root / "runtime" / "data" / "estate_access_truth.json",
    ]
    account_ids: list[str] = []

    def walk(obj: Any) -> None:
        if len(account_ids) >= limit:
            return
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"accountId", "account_id", "id", "userId"} and value:
                    text = str(value)
                    if len(text) > 8 and text not in account_ids:
                        account_ids.append(text)
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    for path in candidates:
        walk(read_json(path, {}))
    return account_ids[:limit]


def directory_ids_from_admin(org_id: str, token: str) -> tuple[list[str], list[dict[str, Any]]]:
    directory_ids: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    configured = os.getenv("ATLASSIAN_DIRECTORY_IDS") or os.getenv("ATLASSIAN_DIRECTORY_ID") or ""
    for value in [part.strip() for part in configured.split(",") if part.strip()]:
        if value not in directory_ids:
            directory_ids.append(value)

    endpoints = [
        ("GET", f"{API_ADMIN_HOST}/v2/orgs/{urllib.parse.quote(org_id)}/directories?limit=20", None, "directories"),
        ("POST", f"{API_ADMIN_HOST}/v2/orgs/{urllib.parse.quote(org_id)}/workspaces", {}, "workspaces"),
    ]
    for method, url, body, name in endpoints:
        ok, status, payload, error = request_json(method, url, token, body)
        rows = extract_list(payload)
        diagnostics.append({"name": name, "ok": ok, "status": status, "row_count": len(rows), "error": error})
        for value in extract_ids(rows, ["id", "directoryId", "directory_id"]):
            if value not in directory_ids:
                directory_ids.append(value)
        for row in rows:
            directory = row.get("directory") if isinstance(row, dict) else None
            if isinstance(directory, dict):
                value = directory.get("id") or directory.get("directoryId")
                if value and str(value) not in directory_ids:
                    directory_ids.append(str(value))
    return directory_ids, diagnostics


def collect_role_assignments(org_id: str, token: str, directory_ids: list[str], account_ids: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    assignments: list[dict[str, Any]] = []
    users_seen: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []

    for directory_id in directory_ids[:5]:
        users_url = f"{API_ADMIN_HOST}/v2/orgs/{urllib.parse.quote(org_id)}/directories/{urllib.parse.quote(directory_id)}/users?limit=20"
        ok, status, payload, error = request_json("GET", users_url, token)
        rows = extract_list(payload)
        probes.append({"endpoint": "directory_users", "directory_id": directory_id, "ok": ok, "status": status, "count": len(rows), "error": error})
        for row in rows:
            account_id = row.get("accountId") or row.get("account_id") or row.get("id") or row.get("userId")
            if account_id and str(account_id) not in account_ids:
                account_ids.append(str(account_id))
            if account_id:
                users_seen.append({"account_id": str(account_id), "email": row.get("email") or row.get("emailAddress"), "display_name": row.get("displayName") or row.get("name"), "directory_id": directory_id})

        for account_id in account_ids[:30]:
            role_url = f"{API_ADMIN_HOST}/v2/orgs/{urllib.parse.quote(org_id)}/directories/{urllib.parse.quote(directory_id)}/users/{urllib.parse.quote(account_id)}/role-assignments?limit=100"
            ok, status, payload, error = request_json("GET", role_url, token)
            role_rows = extract_list(payload)
            probes.append({"endpoint": "role_assignments", "directory_id": directory_id, "account_id_redacted": account_id[:6] + "...", "ok": ok, "status": status, "count": len(role_rows), "error": error})
            if ok:
                for role in role_rows:
                    role["_account_id"] = account_id
                    role["_directory_id"] = directory_id
                    assignments.append(role)
            time.sleep(0.03)
    return assignments, users_seen, probes


def role_text(role: dict[str, Any]) -> str:
    return json.dumps(role, ensure_ascii=False).lower()


def role_is_admin_candidate(role: dict[str, Any]) -> bool:
    text = role_text(role)
    admin_labels = ["admin", "administrator", "site-admin", "site_admin", "org-admin", "role"]
    return any(label in text for label in admin_labels)


def map_role_to_site(role: dict[str, Any], sites: list[dict[str, Any]]) -> dict[str, Any] | None:
    text = role_text(role)
    for site in sites:
        candidates = [site.get("site_key"), site.get("name"), site.get("url"), site.get("cloud_id")]
        for value in candidates:
            if value and str(value).lower() in text:
                return site
    return None


def contacts_from_assignments(assignments: list[dict[str, Any]], users_seen: list[dict[str, Any]], sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user_by_id = {u.get("account_id"): u for u in users_seen if u.get("account_id")}
    contacts: list[dict[str, Any]] = []
    seen = set()
    for role in assignments:
        if not role_is_admin_candidate(role):
            continue
        account_id = role.get("_account_id")
        directory_id = role.get("_directory_id")
        site = map_role_to_site(role, sites)
        if not site:
            continue
        user = user_by_id.get(account_id, {})
        key = (site.get("site_key"), account_id, directory_id)
        if key in seen:
            continue
        seen.add(key)
        contacts.append({
            "site_key": site.get("site_key"),
            "site_name": site.get("name"),
            "site_url": site.get("url"),
            "account_id": account_id,
            "email": user.get("email"),
            "display_name": user.get("display_name"),
            "directory_id": directory_id,
            "role_source": "atlassian_admin_v2_user_role_assignments",
            "verification": "live_endpoint_confirmed",
        })
    return contacts


def collect_admin_contacts(root: Path | None = None, write_output: bool = True) -> dict[str, Any]:
    """Compatibility entrypoint owned by the current estate resource authority builder."""
    from app.builders.estate_resource_authority import refresh_estate_resource_authority
    result = refresh_estate_resource_authority(root=root or ROOT, write_output=write_output)
    return result.get("contacts", result)


if __name__ == "__main__":
    payload = collect_admin_contacts()
    print(json.dumps({"status": payload.get("status"), "summary": payload.get("summary", {})}, indent=2))
