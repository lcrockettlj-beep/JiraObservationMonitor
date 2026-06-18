from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import auth

BASE_DIR = Path(__file__).resolve().parent
REPORT_JSON = BASE_DIR / "auth_verification_report.json"
REPORT_TXT = BASE_DIR / "auth_verification_report.txt"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _resource_row(item: Dict[str, Any]) -> Dict[str, Any]:
    scopes = item.get("scopes", []) or []
    return {
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "url": item.get("url", ""),
        "scopes": list(scopes) if isinstance(scopes, list) else [],
    }


def build_report() -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "generated_at_utc": _iso_now(),
        "oauth": {
            "configured": False,
            "token_file_present": False,
            "access_token_present": False,
            "refresh_token_present": False,
            "token_expired": None,
            "resources_ok": False,
            "resource_count": 0,
            "resources": [],
            "error": None,
        },
        "admin_api": {
            "api_key_present": False,
            "org_id_present": False,
            "orgs_ok": False,
            "org_count": 0,
            "orgs": [],
            "error": None,
        },
    }

    # OAuth / Jira side
    try:
        config = auth.get_config()
        report["oauth"]["configured"] = True
        report["oauth"]["config"] = {
            "client_id_present": bool(config.get("client_id")),
            "client_secret_present": bool(config.get("client_secret")),
            "redirect_uri": config.get("redirect_uri", ""),
            "scopes": config.get("scopes", ""),
        }
        token_data = auth.load_token_data()
        report["oauth"]["token_file_present"] = bool(token_data)
        report["oauth"]["access_token_present"] = bool(token_data.get("access_token"))
        report["oauth"]["refresh_token_present"] = bool(token_data.get("refresh_token"))
        report["oauth"]["token_expired"] = auth.token_is_expired(token_data) if token_data else None
        token = auth.get_valid_access_token()
        report["oauth"]["validated_access_token_present"] = bool(token)
        resources = auth.get_accessible_jira_resources(token)
        report["oauth"]["resources_ok"] = True
        report["oauth"]["resource_count"] = len(resources)
        report["oauth"]["resources"] = [_resource_row(item) for item in resources if isinstance(item, dict)]
    except Exception as exc:
        report["oauth"]["error"] = str(exc)

    # Admin API side
    try:
        api_key = auth.get_admin_api_key(required=False)
        org_id = auth.get_admin_org_id(required=False)
        report["admin_api"]["api_key_present"] = bool(api_key)
        report["admin_api"]["org_id_present"] = bool(org_id)
        if api_key:
            orgs = auth.get_admin_orgs()
            report["admin_api"]["orgs_ok"] = True
            report["admin_api"]["org_count"] = len(orgs)
            report["admin_api"]["orgs"] = [
                {
                    "id": item.get("id", ""),
                    "name": item.get("name", "") or item.get("attributes", {}).get("name", ""),
                }
                for item in orgs if isinstance(item, dict)
            ]
    except Exception as exc:
        report["admin_api"]["error"] = str(exc)

    return report


def _save_report(report: Dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines: List[str] = []
    lines.append("Atlassian Auth Verification Report")
    lines.append("================================")
    lines.append(f"Generated UTC: {report.get('generated_at_utc', '')}")
    lines.append("")
    oauth = report.get("oauth", {})
    lines.append("OAuth / Jira 3LO")
    lines.append("-----------------")
    lines.append(f"Configured: {oauth.get('configured')}")
    lines.append(f"Token file present: {oauth.get('token_file_present')}")
    lines.append(f"Access token present: {oauth.get('access_token_present')}")
    lines.append(f"Refresh token present: {oauth.get('refresh_token_present')}")
    lines.append(f"Token expired: {oauth.get('token_expired')}")
    lines.append(f"Resources OK: {oauth.get('resources_ok')}")
    lines.append(f"Resource count: {oauth.get('resource_count')}")
    if oauth.get("error"):
        lines.append(f"OAuth error: {oauth.get('error')}")
    resources = _safe_list(oauth.get("resources"))
    if resources:
        lines.append("")
        lines.append("Accessible Jira resources:")
        for idx, item in enumerate(resources, start=1):
            if not isinstance(item, dict):
                continue
            lines.append(f"  [{idx}] {item.get('name', '')} | {item.get('url', '')} | {item.get('id', '')}")
    lines.append("")
    admin = report.get("admin_api", {})
    lines.append("Admin API")
    lines.append("---------")
    lines.append(f"Admin API key present: {admin.get('api_key_present')}")
    lines.append(f"Admin org id present: {admin.get('org_id_present')}")
    lines.append(f"Orgs OK: {admin.get('orgs_ok')}")
    lines.append(f"Org count: {admin.get('org_count')}")
    if admin.get("error"):
        lines.append(f"Admin API error: {admin.get('error')}")
    orgs = _safe_list(admin.get("orgs"))
    if orgs:
        lines.append("")
        lines.append("Admin organizations:")
        for idx, item in enumerate(orgs, start=1):
            if not isinstance(item, dict):
                continue
            lines.append(f"  [{idx}] {item.get('name', '')} | {item.get('id', '')}")

    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        report = build_report()
        _save_report(report)
        print("Auth verification complete.")
        print(f"JSON: {REPORT_JSON}")
        print(f"TXT : {REPORT_TXT}")
        oauth = report.get("oauth", {})
        admin = report.get("admin_api", {})
        print(f"OAuth configured: {oauth.get('configured')}")
        print(f"OAuth resources OK: {oauth.get('resources_ok')} | count={oauth.get('resource_count')}")
        print(f"Admin API key present: {admin.get('api_key_present')}")
        print(f"Admin orgs OK: {admin.get('orgs_ok')} | count={admin.get('org_count')}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
