from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "static" / "data" / "operational_console_status.json"
UI_VIEW = ROOT / "static" / "data" / "operational_console_ui_view.json"
DRILLDOWNS = ROOT / "static" / "data" / "operational_console_drilldowns.json"
REPORT = ROOT / "reports" / "operational_console_dark_ui_and_drilldown_pack_v1_status.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_ui_view(status: dict) -> dict:
    cards = status.get("cards", {}) if isinstance(status, dict) else {}
    summary = status.get("summary", {}) if isinstance(status, dict) else {}
    return {
        "schema": "jom-operational-console-ui-view-v1",
        "generated_at_utc": now_utc(),
        "source_generated_at_utc": status.get("generated_at_utc"),
        "overall_status": status.get("overall_status"),
        "cards": {
            "scheduler": cards.get("scheduler"),
            "reliability": cards.get("source_reliability"),
            "runtime": cards.get("runtime_refresh"),
            "sites": cards.get("site_registry"),
        },
        "badges": {
            "scheduler_ok": summary.get("scheduler_ok"),
            "reliability_ok": summary.get("source_reliability_ok"),
            "advisory_count": summary.get("runtime_advisory_count"),
            "issue_count": summary.get("source_reliability_issue_count"),
            "monitored_site_count": summary.get("monitored_site_count"),
            "discovered_site_count": summary.get("discovered_site_count"),
        },
    }


def build_drilldowns(status: dict) -> dict:
    cards = status.get("cards", {}) if isinstance(status, dict) else {}
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    runtime = read_json(ROOT / "static" / "data" / "runtime_refresh_status.json") or {}
    registry = read_json(ROOT / "static" / "data" / "site_registry.json") or {}
    user_footprint = read_json(ROOT / "static" / "data" / "user_footprint.json") or {}
    named_access = read_json(ROOT / "static" / "data" / "named_access_truth_v2.json") or {}

    registry_sites = []
    if isinstance(registry, dict):
        for site in registry.get("sites", []):
            if isinstance(site, dict):
                registry_sites.append({
                    "key": site.get("site_key") or site.get("key") or site.get("site"),
                    "classification": site.get("classification"),
                    "is_monitored": site.get("is_monitored"),
                    "cloud_id": site.get("cloud_id"),
                    "url": site.get("url") or site.get("site_url"),
                })

    return {
        "schema": "jom-operational-console-drilldowns-v1",
        "generated_at_utc": now_utc(),
        "panels": {
            "scheduler": {"title": "Scheduler runtime", "summary": cards.get("scheduler")},
            "source_reliability": {
                "title": "Source reliability",
                "overall_status": reliability.get("overall_status"),
                "summary": reliability.get("summary"),
                "issues": reliability.get("issues") or [],
                "advisories": reliability.get("advisories") or [],
                "alignment": reliability.get("alignment") or {},
            },
            "runtime_refresh": {"title": "Runtime refresh", "summary": cards.get("runtime_refresh"), "raw_status": runtime},
            "site_registry": {"title": "Site registry", "summary": registry.get("summary") if isinstance(registry, dict) else {}, "sites": registry_sites},
            "user_footprint": {"title": "User footprint", "summary": {"source_status": user_footprint.get("source_status"), "users": user_footprint.get("users") or user_footprint.get("user_count"), "assignments": user_footprint.get("assignments") or user_footprint.get("assignment_count")}},
            "named_access": {"title": "Named access truth", "summary": {"source_status": named_access.get("source_status"), "safe": named_access.get("safe"), "generated_at_utc": named_access.get("generated_at_utc")}},
        },
    }


def main() -> int:
    status = read_json(STATUS)
    if not isinstance(status, dict):
        raise SystemExit("static/data/operational_console_status.json is missing or unreadable. Run the Operational Console UI Alignment Pack first.")
    ui_view = build_ui_view(status)
    drilldowns = build_drilldowns(status)
    write_json(UI_VIEW, ui_view)
    write_json(DRILLDOWNS, drilldowns)
    ok = ui_view.get("overall_status") == "ok" and ui_view.get("badges", {}).get("scheduler_ok") is True and ui_view.get("badges", {}).get("reliability_ok") is True
    report = {"schema": "jom-operational-console-dark-ui-and-drilldown-pack-v1-status", "generated_at_utc": now_utc(), "status": "ok" if ok else "attention", "outputs": [str(UI_VIEW), str(DRILLDOWNS)], "ui_view_summary": ui_view.get("badges"), "overall_status": ui_view.get("overall_status")}
    write_json(REPORT, report)
    print(json.dumps(report, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
