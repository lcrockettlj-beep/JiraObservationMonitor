from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_FILE = BASE_DIR / "latest_run_admin_enriched.json"
DEFAULT_OUTPUT_FILE = BASE_DIR / "latest_run_alerted.json"
DEFAULT_OUTPUT_PRETTY_FILE = BASE_DIR / "latest_run_alerted_pretty.json"

DEFAULT_RULES = {
    "unresolved_warning_threshold": 25,
    "unresolved_critical_threshold": 100,
    "managed_disabled_critical": 1,
    "mfa_disabled_warning": 1,
    "not_in_userbase_warning": 1,
    "zero_sites_critical": True,
    "zero_users_warning": True,
}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Input runtime file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Unable to read JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Input payload is not a JSON object: {path}")
    return payload


def _save_json(path: Path, data: Dict[str, Any], indent: Optional[int] = None) -> None:
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")


def _site_alert(scope: str, site: Dict[str, Any], severity: str, title: str, reason: str, value: Any = None) -> Dict[str, Any]:
    return {
        "severity": severity,
        "scope": scope,
        "site_key": site.get("site") or site.get("site_key") or "",
        "site_name": site.get("site_name") or site.get("name") or site.get("site") or "",
        "title": title,
        "reason": reason,
        "value": value,
    }


def _estate_alert(severity: str, title: str, reason: str, value: Any = None) -> Dict[str, Any]:
    return {
        "severity": severity,
        "scope": "estate",
        "title": title,
        "reason": reason,
        "value": value,
    }


def build_alerts(payload: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    estate = _safe_dict(payload.get("estate"))
    sites = [row for row in _safe_list(payload.get("sites")) if isinstance(row, dict)]
    alerts: List[Dict[str, Any]] = []

    total_sites = _to_int(estate.get("total_sites"), len(sites))
    total_users = _to_int(estate.get("total_users"), _to_int(payload.get("users_row_count"), 0))
    managed_disabled_accounts = _to_int(estate.get("managed_disabled_accounts"), 0)
    mfa_disabled_accounts = _to_int(estate.get("mfa_disabled_accounts"), 0)
    not_in_userbase_count = _to_int(estate.get("not_in_userbase_count"), 0)

    if rules.get("zero_sites_critical", True) and total_sites <= 0:
        alerts.append(_estate_alert("critical", "No tracked Jira sites", "The runtime payload reports zero tracked sites.", total_sites))

    if rules.get("zero_users_warning", True) and total_users <= 0:
        alerts.append(_estate_alert("warning", "No runtime users detected", "The runtime payload reports zero users.", total_users))

    if managed_disabled_accounts >= _to_int(rules.get("managed_disabled_critical", 1), 1):
        alerts.append(_estate_alert("critical", "Managed disabled accounts detected", "Managed disabled accounts are present in the latest admin-enriched runtime payload.", managed_disabled_accounts))

    if mfa_disabled_accounts >= _to_int(rules.get("mfa_disabled_warning", 1), 1):
        alerts.append(_estate_alert("warning", "MFA disabled accounts detected", "Accounts with MFA disabled were detected in the latest admin-enriched runtime payload.", mfa_disabled_accounts))

    if not_in_userbase_count >= _to_int(rules.get("not_in_userbase_warning", 1), 1):
        alerts.append(_estate_alert("warning", "Accounts not in userbase detected", "Some admin-enriched accounts are flagged as not in the userbase.", not_in_userbase_count))

    unresolved_warn = _to_int(rules.get("unresolved_warning_threshold", 25), 25)
    unresolved_crit = _to_int(rules.get("unresolved_critical_threshold", 100), 100)

    for site in sites:
        site_name = site.get("site_name") or site.get("name") or site.get("site") or "site"
        status = str(site.get("status") or "").strip().lower()
        unresolved = _to_int(site.get("issue_count_unresolved"), 0)
        reason = str(site.get("reason") or "").strip()

        if status == "critical":
            alerts.append(_site_alert("site", site, "critical", f"Critical site: {site_name}", reason or "The site is marked critical in the runtime payload.", unresolved))
        elif status in {"warning", "degraded", "caution"}:
            alerts.append(_site_alert("site", site, "warning", f"Warning site: {site_name}", reason or "The site is marked warning/degraded in the runtime payload.", unresolved))

        if unresolved >= unresolved_crit:
            alerts.append(_site_alert("site", site, "critical", f"High unresolved issue load: {site_name}", f"Unresolved issues are at or above the critical threshold ({unresolved_crit}).", unresolved))
        elif unresolved >= unresolved_warn:
            alerts.append(_site_alert("site", site, "warning", f"Rising unresolved issue load: {site_name}", f"Unresolved issues are at or above the warning threshold ({unresolved_warn}).", unresolved))

        if reason and any(token in reason.lower() for token in ["permission", "forbidden", "unauthorized"]):
            alerts.append(_site_alert("site", site, "warning", f"Permission-limited site: {site_name}", reason, unresolved))

    critical = [a for a in alerts if a.get("severity") == "critical"]
    warning = [a for a in alerts if a.get("severity") == "warning"]
    info = [a for a in alerts if a.get("severity") == "info"]
    critical_sites = [a for a in critical if a.get("scope") == "site"]
    warning_sites = [a for a in warning if a.get("scope") == "site"]

    top_risks = critical[:5] + warning[:5]
    summary = {
        "critical_count": len(critical),
        "warning_count": len(warning),
        "info_count": len(info),
        "site_critical_count": len(critical_sites),
        "site_warning_count": len(warning_sites),
    }

    return {
        "generated_at_utc": _iso_now(),
        "rules": dict(rules),
        "summary": summary,
        "critical": critical,
        "warning": warning,
        "info": info,
        "critical_sites": critical_sites,
        "warning_sites": warning_sites,
        "top_risks": top_risks,
    }


def apply_alerts(payload: Dict[str, Any], alerts_bundle: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    data["runtime_alerts"] = alerts_bundle
    data["critical_sites"] = alerts_bundle.get("critical_sites", [])
    data["warning_sites"] = alerts_bundle.get("warning_sites", [])

    intelligence_summary = _safe_dict(data.get("intelligence_summary"))
    intelligence_summary["top_risks"] = alerts_bundle.get("top_risks", [])
    intelligence_summary["runtime_alert_summary"] = alerts_bundle.get("summary", {})
    data["intelligence_summary"] = intelligence_summary

    estate = _safe_dict(data.get("estate"))
    alert_summary = _safe_dict(alerts_bundle.get("summary"))
    estate["runtime_critical_alert_count"] = alert_summary.get("critical_count", 0)
    estate["runtime_warning_alert_count"] = alert_summary.get("warning_count", 0)
    estate["runtime_site_critical_count"] = alert_summary.get("site_critical_count", 0)
    estate["runtime_site_warning_count"] = alert_summary.get("site_warning_count", 0)
    data["estate"] = estate
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply alert rules to the admin-enriched runtime payload.")
    parser.add_argument("--input-file", default=str(DEFAULT_INPUT_FILE))
    parser.add_argument("--output-file", default=str(DEFAULT_OUTPUT_FILE))
    parser.add_argument("--output-pretty-file", default=str(DEFAULT_OUTPUT_PRETTY_FILE))
    args = parser.parse_args()
    try:
        payload = _load_json(Path(args.input_file))
        alerts_bundle = build_alerts(payload, DEFAULT_RULES)
        alerted_payload = apply_alerts(payload, alerts_bundle)
        _save_json(Path(args.output_file), alerted_payload, indent=None)
        _save_json(Path(args.output_pretty_file), alerted_payload, indent=2)
        summary = alerts_bundle.get("summary", {})
        print("Alert rules applied.")
        print(f"Critical alerts: {summary.get('critical_count', 0)}")
        print(f"Warning alerts: {summary.get('warning_count', 0)}")
        print(f"Critical sites: {summary.get('site_critical_count', 0)}")
        print(f"Warning sites: {summary.get('site_warning_count', 0)}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
