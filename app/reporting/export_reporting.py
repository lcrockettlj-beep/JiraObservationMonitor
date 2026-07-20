from __future__ import annotations
import csv
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default
    return default


def first_dict(*items: Any) -> Dict[str, Any]:
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def load_sources() -> Dict[str, Any]:
    root = repo_root()
    static = root / "static" / "data"
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "registry": first_dict(read_json(static / "site_registry.json", {}), read_json(root / "latest_run.json", {}).get("site_registry", {})),
        "estate_product_access": first_dict(read_json(static / "estate_product_access.json", {})),
        "user_footprint": first_dict(read_json(static / "user_footprint.json", {})),
        "admin_truth": first_dict(read_json(static / "admin_truth_v2.json", {})),
        "runtime_status": first_dict(read_json(static / "runtime_refresh_status.json", {}), read_json(static / "runtime_execution_status.json", {})),
        "source_reliability": first_dict(read_json(static / "source_reliability_status.json", {})),
        "source_freshness": first_dict(read_json(static / "source_freshness_audit.json", {})),
        "operator_summary": first_dict(read_json(root / "latest_run_safe_partial.json", {}).get("operator_summary", {})),
    }


def sites_from_registry(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    sites = registry.get("sites")
    if isinstance(sites, list):
        return [s for s in sites if isinstance(s, dict)]
    if isinstance(sites, dict):
        return [dict(v, key=k) if isinstance(v, dict) else {"key": k, "value": v} for k, v in sites.items()]
    return []


def site_key(site: Dict[str, Any]) -> str:
    for key in ("key", "site_key", "slug", "name", "site", "url"):
        value = site.get(key)
        if value:
            text = str(value).lower().replace("https://", "").replace("http://", "")
            text = text.replace(".atlassian.net", "").split("/")[0]
            return text.strip()
    return "unknown-site"


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "monitored", "active")
    return bool(value)


def registry_summary(registry: Dict[str, Any]) -> Dict[str, Any]:
    summary = registry.get("summary") if isinstance(registry.get("summary"), dict) else {}
    sites = sites_from_registry(registry)
    total = summary.get("total_sites", len(sites))
    monitored = summary.get("monitored_count")
    discovered = summary.get("discovered_count")
    if monitored is None:
        monitored = sum(1 for s in sites if boolish(s.get("monitored")) or str(s.get("state", "")).lower() == "monitored")
    if discovered is None:
        discovered = max(0, int(total or 0) - int(monitored or 0))
    return {"total_sites": total or 0, "monitored_sites": monitored or 0, "discovered_sites": discovered or 0}


def product_access_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    sites = data.get("sites") if isinstance(data.get("sites"), list) else []
    return {
        "product_access_sites": summary.get("site_count", summary.get("sites", len(sites))),
        "roles": len(data.get("roles", [])) if isinstance(data.get("roles"), list) else summary.get("roles", 0),
        "errors": len(data.get("errors", [])) if isinstance(data.get("errors"), list) else summary.get("errors", 0),
    }


def user_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    users = data.get("users") if isinstance(data.get("users"), list) else []
    return {
        "users_analyzed": summary.get("users_analyzed", len(users)),
        "named_unique_users": summary.get("named_unique_users", 0),
        "total_product_access_assignments": summary.get("total_product_access_assignments", 0),
        "safe_to_show_named_access_ui": data.get("safe_to_show_named_access_ui", data.get("source_status", "unknown")),
    }


def runtime_summary(runtime: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "runtime_status": runtime.get("last_result_status", runtime.get("status", runtime.get("state", "unknown"))),
        "last_finished_at_utc": runtime.get("last_finished_at_utc", runtime.get("generated_at_utc", "unknown")),
        "source_reliability": source.get("status", source.get("overall_status", "unknown")),
        "issue_count": source.get("issue_count", source.get("issues", 0)),
    }


def build_snapshot() -> Dict[str, Any]:
    src = load_sources()
    reg = registry_summary(src["registry"])
    prod = product_access_summary(src["estate_product_access"])
    users = user_summary(src["user_footprint"])
    runtime = runtime_summary(src["runtime_status"], src["source_reliability"])
    alert_count = 0
    op = src.get("operator_summary") or {}
    if isinstance(op.get("alert_summary"), dict):
        alert_count = op["alert_summary"].get("count", op["alert_summary"].get("total", 0)) or 0
    health = 100
    health -= min(int(reg.get("discovered_sites") or 0) * 2, 20)
    health -= min(int(alert_count) * 5, 30)
    health = max(0, min(100, health))
    return {
        "generated_at_utc": src["generated_at_utc"],
        "estate_health_score": health,
        "registry": reg,
        "product_access": prod,
        "users": users,
        "runtime": runtime,
        "active_alerts": alert_count,
        "sources": src,
    }


def executive_report() -> Dict[str, Any]:
    snap = build_snapshot()
    findings = []
    reg = snap["registry"]
    if reg["discovered_sites"]:
        findings.append(f"{reg['discovered_sites']} discovered sites require monitoring/governance review.")
    if snap["active_alerts"]:
        findings.append(f"{snap['active_alerts']} active alert(s) require operational review.")
    if not findings:
        findings.append("No critical source-backed issue detected in the current operational snapshot.")
    return {
        "report_type": "executive_summary",
        "generated_at_utc": snap["generated_at_utc"],
        "estate_health_score": snap["estate_health_score"],
        "runtime_status": snap["runtime"].get("runtime_status"),
        "active_alerts": snap["active_alerts"],
        "total_sites": snap["registry"]["total_sites"],
        "monitored_sites": snap["registry"]["monitored_sites"],
        "discovered_sites": snap["registry"]["discovered_sites"],
        "users_analyzed": snap["users"]["users_analyzed"],
        "key_findings": findings,
    }


def estate_report() -> Dict[str, Any]:
    snap = build_snapshot()
    sites = []
    for s in sites_from_registry(snap["sources"]["registry"]):
        key = site_key(s)
        state = "monitored" if boolish(s.get("monitored")) or str(s.get("state", "")).lower() == "monitored" else "discovered"
        sites.append({
            "site_key": key,
            "display_name": s.get("name", s.get("display_name", key)),
            "url": s.get("url", s.get("site_url", "")),
            "state": state,
            "monitored": state == "monitored",
            "source": s.get("source", "registry"),
        })
    return {"report_type": "estate_summary", "generated_at_utc": snap["generated_at_utc"], "summary": snap["registry"], "sites": sites}


def admin_report() -> Dict[str, Any]:
    snap = build_snapshot()
    return {
        "report_type": "governance_summary",
        "generated_at_utc": snap["generated_at_utc"],
        "users": snap["users"],
        "registry": snap["registry"],
        "runtime": snap["runtime"],
        "product_access": snap["product_access"],
        "admin_truth_keys": sorted(list((snap["sources"].get("admin_truth") or {}).keys())),
    }


def site_report(site: str) -> Dict[str, Any]:
    estate = estate_report()
    snap = build_snapshot()
    key = str(site).lower()
    match = None
    for s in estate["sites"]:
        if s["site_key"] == key:
            match = s
            break
    return {
        "report_type": "site_snapshot",
        "generated_at_utc": snap["generated_at_utc"],
        "site_key": key,
        "registry_match": match,
        "runtime": snap["runtime"],
        "active_alerts": snap["active_alerts"],
        "product_access_summary": snap["product_access"],
        "user_summary": snap["users"],
    }


def to_csv(report: Dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["field", "value"])
    def emit(prefix: str, value: Any):
        if isinstance(value, dict):
            for k, v in value.items():
                emit(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(value, list):
            if value and all(isinstance(i, dict) for i in value):
                writer.writerow([prefix, json.dumps(value, ensure_ascii=False)])
            else:
                writer.writerow([prefix, json.dumps(value, ensure_ascii=False)])
        else:
            writer.writerow([prefix, value])
    emit("", report)
    return buf.getvalue()


def to_html(report: Dict[str, Any]) -> str:
    title = str(report.get("report_type", "JOM Report")).replace("_", " ").title()
    body = html.escape(json.dumps(report, indent=2, ensure_ascii=False))
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f5f7;color:#172b4d;margin:0;padding:32px}}main{{max-width:1100px;margin:auto;background:#fff;border:1px solid #dfe1e6;border-radius:16px;padding:28px;box-shadow:0 12px 32px rgba(9,30,66,.12)}}h1{{margin-top:0}}pre{{white-space:pre-wrap;background:#f7f8f9;border:1px solid #dfe1e6;border-radius:12px;padding:18px;overflow:auto}}</style></head><body><main><h1>{html.escape(title)}</h1><p>Generated by Jira Observation Monitor.</p><pre>{body}</pre></main></body></html>"""


def get_report(kind: str, site: str | None = None) -> Dict[str, Any]:
    if kind == "executive":
        return executive_report()
    if kind == "estate":
        return estate_report()
    if kind == "admin":
        return admin_report()
    if kind == "site":
        return site_report(site or "unknown")
    return {"report_type": "unknown", "error": f"Unsupported report kind: {kind}"}
