from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "static" / "data"

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2, "ok": 3}


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


def add_alert(alerts: List[Dict[str, Any]], level: str, category: str, title: str, reason: str, source: str, value: Any = None, action: str = "Review source") -> None:
    alerts.append({
        "level": level,
        "category": category,
        "title": title,
        "reason": reason,
        "source": source,
        "value": value,
        "recommended_action": action,
    })


def sort_alerts(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(alerts, key=lambda item: (SEVERITY_RANK.get(str(item.get("level", "info")).lower(), 9), str(item.get("category", "")), str(item.get("title", ""))))


def summarise_alerts(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "critical": len([a for a in alerts if a.get("level") == "critical"]),
        "warning": len([a for a in alerts if a.get("level") == "warning"]),
        "info": len([a for a in alerts if a.get("level") == "info"]),
        "total": len(alerts),
    }


def derive_posture(summary: Dict[str, Any]) -> str:
    if summary.get("critical", 0) > 0:
        return "critical"
    if summary.get("warning", 0) > 0:
        return "warning"
    return "ok"


def compact_runtime_status(runtime: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(runtime, dict):
        return {"state": "unknown", "running": False}
    return {
        "state": runtime.get("state", "unknown"),
        "running": bool(runtime.get("running", False)),
        "last_action": runtime.get("last_action"),
        "last_started_at_utc": runtime.get("last_started_at_utc"),
        "last_finished_at_utc": runtime.get("last_finished_at_utc"),
        "last_result_status": runtime.get("last_result_status"),
        "last_error": runtime.get("last_error"),
    }


def build_alerts() -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    runtime = load_json("runtime_execution_status.json", {})
    if isinstance(runtime, dict):
        if runtime.get("running") is True:
            add_alert(alerts, "info", "runtime", "Runtime execution in progress", "A runtime action is currently running.", "runtime_execution_status.json", runtime.get("last_action"), "Wait for the current runtime action to finish")
        if runtime.get("state") == "failed" or runtime.get("last_result_status") == "failed":
            add_alert(alerts, "critical", "runtime", "Last runtime execution failed", str(runtime.get("last_error") or "Runtime status indicates failure."), "runtime_execution_status.json", action="Review runtime status and rerun after correction")

    reliability = load_json("source_reliability_status.json", {})
    issue_count = safe_int(reliability.get("issue_count"), 0) if isinstance(reliability, dict) else 0
    if issue_count > 0:
        add_alert(alerts, "warning", "source", "Source reliability has issues", "Source reliability audit reports one or more issues.", "source_reliability_status.json", issue_count, "Open source reliability detail and resolve listed causes")

    freshness = load_json("source_freshness_audit.json", {})
    counts = freshness.get("counts", {}) if isinstance(freshness, dict) else {}
    stale = safe_int(counts.get("STALE"), 0)
    missing = safe_int(counts.get("MISSING"), 0)
    aging = safe_int(counts.get("AGING"), 0)
    if missing > 0:
        add_alert(alerts, "critical", "freshness", "Missing runtime sources", "One or more expected runtime source files are missing.", "source_freshness_audit.json", missing, "Run runtime refresh or source recovery")
    if stale > 0:
        add_alert(alerts, "warning", "freshness", "Stale runtime sources", "One or more runtime source files are stale.", "source_freshness_audit.json", stale, "Run runtime refresh")
    if aging > 0:
        add_alert(alerts, "info", "freshness", "Aging runtime sources", "Some runtime source files are aging but not stale.", "source_freshness_audit.json", aging, "Monitor; refresh if operator context requires current data")

    admin_truth = load_json("admin_truth_v2.json", {})
    if isinstance(admin_truth, dict):
        admin_status = str(admin_truth.get("status", "")).lower()
        admin_severity = str(admin_truth.get("severity", "")).lower()
        if admin_status and admin_status not in {"aligned", "ok", "healthy"}:
            add_alert(alerts, "warning", "admin", "Admin truth requires review", "Admin truth is not reporting an aligned state.", "admin_truth_v2.json", admin_status, "Review Admin Truth endpoint")
        elif admin_severity and admin_severity not in {"ok", "info"}:
            add_alert(alerts, "warning", "admin", "Admin truth severity is elevated", "Admin truth severity is not ok.", "admin_truth_v2.json", admin_severity, "Review Admin Truth endpoint")

    registry = load_json("site_registry.json", {})
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    discovered = [s for s in sites if isinstance(s, dict) and s.get("classification") == "discovered"]
    if discovered:
        add_alert(alerts, "info", "registry", "Discovered sites need classification", "One or more discovered sites are not yet monitored.", "site_registry.json", len(discovered), "Review site registry and onboarding decisions")

    return sort_alerts(alerts)


def build_operator_summary() -> Dict[str, Any]:
    alerts = build_alerts()
    summary = summarise_alerts(alerts)
    runtime = compact_runtime_status(load_json("runtime_execution_status.json", {}))
    history = load_json("runtime_execution_history.json", [])
    admin_truth = load_json("admin_truth_v2.json", {})
    freshness = load_json("source_freshness_audit.json", {})
    reliability = load_json("source_reliability_status.json", {})

    return {
        "schema": "jom-operator-summary-v1",
        "generated_at_utc": now_utc(),
        "posture": derive_posture(summary),
        "alert_summary": summary,
        "top_alerts": alerts[:5],
        "runtime": runtime,
        "observability": {
            "history_count": len(history) if isinstance(history, list) else 0,
            "last_history_event": history[-1] if isinstance(history, list) and history else None,
        },
        "source_health": {
            "freshness_overall": freshness.get("overall_state") if isinstance(freshness, dict) else None,
            "freshness_counts": freshness.get("counts", {}) if isinstance(freshness, dict) else {},
            "reliability_issue_count": reliability.get("issue_count") if isinstance(reliability, dict) else None,
        },
        "admin_truth": {
            "status": admin_truth.get("status") if isinstance(admin_truth, dict) else None,
            "severity": admin_truth.get("severity") if isinstance(admin_truth, dict) else None,
        },
    }


def build_operator_surface() -> Dict[str, Any]:
    alerts = build_alerts()
    summary = summarise_alerts(alerts)
    runtime = load_json("runtime_execution_status.json", {})
    registry = load_json("site_registry.json", {})
    freshness = load_json("source_freshness_audit.json", {})
    reliability = load_json("source_reliability_status.json", {})
    admin_truth = load_json("admin_truth_v2.json", {})
    user_footprint = load_json("user_footprint.json", {})
    estate_product_access = load_json("estate_product_access.json", {})
    history = load_json("runtime_execution_history.json", [])

    return {
        "schema": "jom-operator-surface-v1.1",
        "generated_at_utc": now_utc(),
        "posture": derive_posture(summary),
        "alert_summary": summary,
        "alerts": alerts,
        "runtime": compact_runtime_status(runtime),
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
