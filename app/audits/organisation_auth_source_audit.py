from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.builders.organisation_discovery import load_env, read_json, token_file_path, tokens_json_summary


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def audit_organisation_auth_sources() -> Dict[str, Any]:
    env = load_env()
    tokens_path = token_file_path()
    tokens = read_json(tokens_path, {})
    tokens = tokens if isinstance(tokens, dict) else {}
    admin_keys = [
        "ATLASSIAN_ADMIN_API_TOKEN",
        "ATLASSIAN_ADMIN_TOKEN",
        "ATLASSIAN_ORG_API_TOKEN",
        "ATLASSIAN_ORGANISATION_API_TOKEN",
        "ATLASSIAN_ORGANIZATION_API_TOKEN",
    ]
    client_keys = ["ATLASSIAN_CLIENT_ID", "ATLASSIAN_OAUTH_CLIENT_ID"]
    secret_keys = ["ATLASSIAN_CLIENT_SECRET", "ATLASSIAN_OAUTH_CLIENT_SECRET"]
    admin_configured = [key for key in admin_keys if env.get(key)]
    client_configured = [key for key in client_keys if env.get(key)]
    secret_configured = [key for key in secret_keys if env.get(key)]
    t_summary = tokens_json_summary(tokens)
    if admin_configured:
        status = "admin_token_candidate_present"
    elif t_summary.get("access_token_present") or t_summary.get("refresh_token_present"):
        status = "oauth_token_candidate_present"
    else:
        status = "missing"
    return {
        "schema": "jom-atlassian-organisation-auth-source-audit-v1",
        "generated_at_utc": now_utc(),
        "status": status,
        "admin_token_sources_configured": admin_configured,
        "oauth_client_configured": bool(client_configured),
        "oauth_client_secret_configured": bool(secret_configured),
        "tokens_json_summary": t_summary,
        "secrets_exposed": False,
        "static_fallback_used": False,
    }
