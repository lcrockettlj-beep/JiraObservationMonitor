from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ORG_API_URL = "https://" + "api.atlassian.com/admin/v1/orgs"
TOKEN_URL = "https://" + "auth.atlassian.com/oauth/token"

ADMIN_TOKEN_KEYS = (
    "ATLASSIAN_ADMIN_API_KEY",
    "ATLASSIAN_ADMIN_API_TOKEN",
    "ATLASSIAN_ADMIN_TOKEN",
    "ATLASSIAN_ORG_API_TOKEN",
    "ATLASSIAN_ORGANISATION_API_TOKEN",
    "ATLASSIAN_ORGANIZATION_API_TOKEN",
)

CLIENT_ID_KEYS = (
    "ATLASSIAN_CLIENT_ID",
    "ATLASSIAN_OAUTH_CLIENT_ID",
)

CLIENT_SECRET_KEYS = (
    "ATLASSIAN_CLIENT_SECRET",
    "ATLASSIAN_OAUTH_CLIENT_SECRET",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def root_path() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env() -> Dict[str, str]:
    values = dict(os.environ)
    env_path = root_path() / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return payload
    except Exception as exc:
        return {"_read_error": str(exc), "_path": str(path)}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def token_file_path() -> Path:
    return root_path() / "tokens.json"


def secret_present(value: Any) -> bool:
    return bool(str(value or "").strip())


def first_env_value(keys: Tuple[str, ...], env: Dict[str, str]) -> Tuple[str, str]:
    for key in keys:
        value = env.get(key)
        if secret_present(value):
            return key, str(value).strip()
    return "", ""


def tokens_json_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    expires_at = payload.get("expires_at_epoch")
    expired = None
    if payload.get("access_token"):
        try:
            expired = int(expires_at or 0) <= int(time.time()) + 60
        except Exception:
            expired = None
    return {
        "exists": token_file_path().exists(),
        "readable": not bool(payload.get("_read_error")),
        "access_token_present": bool(payload.get("access_token")),
        "refresh_token_present": bool(payload.get("refresh_token")),
        "expires_at_epoch_present": expires_at is not None,
        "expired_or_near_expiry": expired,
        "scope_present": bool(payload.get("scope")),
        "scope": str(payload.get("scope") or ""),
        "value_exposed": False,
    }


def refresh_oauth_token(tokens: Dict[str, Any], env: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    client_id_key, client_id = first_env_value(CLIENT_ID_KEYS, env)
    client_secret_key, client_secret = first_env_value(CLIENT_SECRET_KEYS, env)
    refresh_token = str(tokens.get("refresh_token") or "").strip()

    if not client_id or not client_secret or not refresh_token:
        return tokens, {
            "attempted": False,
            "available": False,
            "reason": "OAuth refresh requires client_id, client_secret, and refresh_token.",
            "client_id_present": bool(client_id),
            "client_secret_present": bool(client_secret),
            "refresh_token_present": bool(refresh_token),
            "value_exposed": False,
        }

    body = json.dumps({
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }).encode("utf-8")

    request = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            raw = response.read().decode("utf-8", errors="replace")
            refreshed = json.loads(raw) if raw else {}
            if not isinstance(refreshed, dict) or not refreshed.get("access_token"):
                return tokens, {
                    "attempted": True,
                    "available": False,
                    "reason": "Refresh response did not contain an access_token.",
                    "value_exposed": False,
                }
            now_epoch = int(time.time())
            updated = dict(tokens)
            updated.update(refreshed)
            updated["saved_at_epoch"] = now_epoch
            try:
                updated["expires_at_epoch"] = now_epoch + int(refreshed.get("expires_in") or 3600)
            except Exception:
                updated["expires_at_epoch"] = now_epoch + 3600
            write_json(token_file_path(), updated)
            return updated, {
                "attempted": True,
                "available": True,
                "client_id_source": client_id_key,
                "client_secret_configured": bool(client_secret_key),
                "refresh_token_rotated": bool(refreshed.get("refresh_token")),
                "value_exposed": False,
            }
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode("utf-8", errors="replace")[:1000]
        return tokens, {
            "attempted": True,
            "available": False,
            "http_status": exc.code,
            "reason": msg,
            "value_exposed": False,
        }
    except Exception as exc:
        return tokens, {
            "attempted": True,
            "available": False,
            "reason": str(exc),
            "value_exposed": False,
        }


def select_token() -> Tuple[str, str, Dict[str, Any]]:
    env = load_env()

    admin_key, admin_token = first_env_value(ADMIN_TOKEN_KEYS, env)
    if admin_token:
        return admin_token, "environment:" + admin_key, {
            "source": "environment",
            "key": admin_key,
            "configured": True,
            "value_exposed": False,
        }

    tokens = read_json(token_file_path(), {})
    tokens = tokens if isinstance(tokens, dict) else {}
    summary = tokens_json_summary(tokens)
    access_token = str(tokens.get("access_token") or "").strip()
    expired = summary.get("expired_or_near_expiry")

    refresh_result: Dict[str, Any] = {"attempted": False, "available": False, "value_exposed": False}
    if access_token and expired is not True:
        return access_token, "tokens.json:access_token", {
            "source": "tokens.json",
            "configured": True,
            "tokens_json": summary,
            "refresh": refresh_result,
            "value_exposed": False,
        }

    if tokens.get("refresh_token"):
        refreshed_tokens, refresh_result = refresh_oauth_token(tokens, env)
        access_token = str(refreshed_tokens.get("access_token") or "").strip()
        refreshed_summary = tokens_json_summary(refreshed_tokens if isinstance(refreshed_tokens, dict) else {})
        if access_token and refresh_result.get("available") is True:
            return access_token, "tokens.json:refreshed_access_token", {
                "source": "tokens.json",
                "configured": True,
                "tokens_json": refreshed_summary,
                "refresh": refresh_result,
                "value_exposed": False,
            }
        summary = refreshed_summary

    return "", "unavailable", {
        "source": "none",
        "environment_admin_token_configured": False,
        "tokens_json": summary,
        "refresh": refresh_result,
        "value_exposed": False,
    }


def http_json(url: str, token: str) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": "JOM Organisation Discovery",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw else {}
        return payload if isinstance(payload, dict) else {"data": payload}


def normalise_org(row: Dict[str, Any]) -> Dict[str, Any]:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    relationships = row.get("relationships") if isinstance(row.get("relationships"), dict) else {}
    links = row.get("links") if isinstance(row.get("links"), dict) else {}
    return {
        "id": row.get("id"),
        "type": row.get("type") or "orgs",
        "name": attributes.get("name") or row.get("name") or row.get("displayName"),
        "attributes": attributes,
        "relationships": relationships,
        "links": links,
        "source": "atlassian_admin_orgs_api",
    }


def rows_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = payload.get("data")
    if isinstance(rows, dict):
        rows = [] if not rows else [rows]
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def collect_organisation_discovery(max_pages: int = 10) -> Dict[str, Any]:
    token, token_source, token_detail = select_token()
    if not token:
        return {
            "schema": "jom-live-organisation-discovery-v1",
            "served_at_utc": now_utc(),
            "status": "unavailable",
            "live_collection": False,
            "authority": "atlassian_admin_organisations_api",
            "source_endpoint": ORG_API_URL,
            "token_source": token_source,
            "token_source_detail": token_detail,
            "organisation_count": None,
            "organisations": [],
            "reason": "No usable Atlassian organisation API access token is available.",
            "static_fallback_used": False,
            "secrets_exposed": False,
        }

    organisations: List[Dict[str, Any]] = []
    pages_seen = 0
    next_url: Optional[str] = ORG_API_URL
    last_payload_keys: List[str] = []

    try:
        while next_url and pages_seen < max_pages:
            pages_seen += 1
            payload = http_json(next_url, token)
            last_payload_keys = sorted(list(payload.keys()))
            for row in rows_from_payload(payload):
                organisations.append(normalise_org(row))
            links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
            next_link = links.get("next")
            next_url = next_link if isinstance(next_link, str) and next_link else None
        return {
            "schema": "jom-live-organisation-discovery-v1",
            "served_at_utc": now_utc(),
            "status": "ok",
            "live_collection": True,
            "authority": "atlassian_admin_organisations_api",
            "source_endpoint": ORG_API_URL,
            "token_source": token_source,
            "token_source_detail": token_detail,
            "organisation_count": len(organisations),
            "organisations": organisations,
            "pages_seen": pages_seen,
            "last_payload_keys": last_payload_keys,
            "static_fallback_used": False,
            "secrets_exposed": False,
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        return {
            "schema": "jom-live-organisation-discovery-v1",
            "served_at_utc": now_utc(),
            "status": "error",
            "live_collection": True,
            "authority": "atlassian_admin_organisations_api",
            "source_endpoint": ORG_API_URL,
            "token_source": token_source,
            "token_source_detail": token_detail,
            "organisation_count": None,
            "organisations": [],
            "http_status": exc.code,
            "error": body,
            "static_fallback_used": False,
            "secrets_exposed": False,
        }
    except Exception as exc:
        return {
            "schema": "jom-live-organisation-discovery-v1",
            "served_at_utc": now_utc(),
            "status": "error",
            "live_collection": True,
            "authority": "atlassian_admin_organisations_api",
            "source_endpoint": ORG_API_URL,
            "token_source": token_source,
            "token_source_detail": token_detail,
            "organisation_count": None,
            "organisations": [],
            "error": str(exc),
            "static_fallback_used": False,
            "secrets_exposed": False,
        }


