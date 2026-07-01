from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "static" / "data"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(filename: str, default: Any = None) -> Any:
    path = DATA_DIR / filename
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc), "_file": filename}


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def add_alert(alerts: List[Dict[str, Any]], level: str, category: str, title: str, reason: str, source: str, value: Any = None) -> None:
    alerts.append({
        "level": level,
        "category": category,
        "title": title,
        "reason": reason,
        "source": source,
        "value": value,
    })


def build_alerts() -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    runtime = load_json("runtime_execution_status.json", {})
    if runtime:
        if runtime.get("running") is True:
            add_alert(alerts, "info", "runtime", "Runtime execution in progress", "A runtime action is currently running.", "runtime_execution_status.json", runtime.get("last_action"))
        if runtime.get("state") == "failed" or runtime.get("last_result_status") == "failed":
            add_alert(alerts, "critical", "runtime", "Last runtime execution failed", str(runtime.get("last_error") or "Runtime status indicates failure."), "runtime_execution_status.json")

    reliability = load_json("source_reliability_status.json", {})
    issue_count = safe_int(reliability.get("issue_count"), 0) if isinstance(reliability, dict) else 0
    if issue_count > 0:
        add_alert(alerts, "warning", "source", "Source reliability has issues", "Source reliability audit reports one or more issues.", "source_reliability_status.json", issue_count)

    freshness = load_json("source_freshness_audit.json", {})
    counts = freshness.get("counts", {}) if isinstance(freshness, dict) else {}
    stale = safe_int(counts.get("STALE"), 0)
    missing = safe_int(counts.get("MISSING"), 0)
    aging = safe_int(counts.get("AGING"), 0)
    if missing > 0:
        add_alert(alerts, "critical", "freshness", "Missing runtime sources", "One or more expected runtime source files are missing.", "source_freshness_audit.json", missing)
    if stale > 0:
        add_alert(alerts, "warning", "freshness", "Stale runtime sources", "One or more runtime source files are stale.", "source_freshness_audit.json", stale)
    if aging > 0:
        add_alert(alerts, "info", "freshness", "Aging runtime sources", "Some runtime source files are aging but not stale.", "source_freshness_audit.json", aging)

    admin_truth = load_json("admin_truth_v2.json", {})
    admin_status = str(admin_truth.get("status", "")).lower() if isinstance(admin_truth, dict) else ""
    admin_severity = str(admin_truth.get("severity", "")).lower() if isinstance(admin_truth, dict) else ""
    if admin_status and admin_status not in {"aligned", "ok", "healthy"}:
        add_alert(alerts, "warning", "admin", "Admin truth requires review", "Admin truth is not reporting an aligned state.", "admin_truth_v2.json", admin_status)
    elif admin_severity and admin_severity not in {"ok", "info"}:
        add_alert(alerts, "warning", "admin", "Admin truth severity is elevated", "Admin truth severity is not ok.", "admin_truth_v2.json", admin_severity)

    registry = load_json("site_registry.json", {})
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    discovered = [s for s in sites if isinstance(s, dict) and s.get("classification") == "discovered"]
    if discovered:
        add_alert(alerts, "info", "registry", "Discovered sites need classification", "One or more discovered sites are not yet monitored.", "site_registry.json", len(discovered))

    return alerts


def summarise_alerts(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "critical": len([a for a in alerts if a.get("level") == "critical"]),
        "warning": len([a for a in alerts if a.get("level") == "warning"]),
        "info": len([a for a in alerts if a.get("level") == "info"]),
        "total": len(alerts),
    }


def build_operator_surface() -> Dict[str, Any]:
    alerts = build_alerts()
    runtime = load_json("runtime_execution_status.json", {})
    registry = load_json("site_registry.json", {})
    freshness = load_json("source_freshness_audit.json", {})
    reliability = load_json("source_reliability_status.json", {})
    admin_truth = load_json("admin_truth_v2.json", {})
    user_footprint = load_json("user_footprint.json", {})
    estate_product_access = load_json("estate_product_access.json", {})
    history = load_json("runtime_execution_history.json", [])

    return {
        "schema": "jom-operator-surface-v1",
        "generated_at_utc": now_utc(),
        "posture": "critical" if summarise_alerts(alerts)["critical"] else "warning" if summarise_alerts(alerts)["warning"] else "ok",
        "alert_summary": summarise_alerts(alerts),
        "alerts": alerts,
        "runtime": runtime,
        "observability": {
            "history_count": len(history) if isinstance(history, list) else 0,
            "recent_history": history[-10:] if isinstance(history, list) else [],
        },
        "sources": {
            "freshness": freshness,
            "reliability": reliability,
        },
        "admin": {
            "truth_status": admin_truth.get("status") if isinstance(admin_truth, dict) else None,
            "truth_severity": admin_truth.get("severity") if isinstance(admin_truth, dict) else None,
            "human_users": admin_truth.get("admin_human_users") if isinstance(admin_truth, dict) else None,
            "api_product_users": admin_truth.get("api_product_users") if isinstance(admin_truth, dict) else None,
        },
        "estate": {
            "registry_summary": registry.get("summary", {}) if isinstance(registry, dict) else {},
            "user_footprint_summary": {
                "users": user_footprint.get("users") if isinstance(user_footprint, dict) else None,
                "assignments": user_footprint.get("assignments") if isinstance(user_footprint, dict) else None,
                "safe": user_footprint.get("safe") if isinstance(user_footprint, dict) else None,
            },
            "product_access_summary": estate_product_access.get("summary", {}) if isinstance(estate_product_access, dict) else {},
        },
    }
