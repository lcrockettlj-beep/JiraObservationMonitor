from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSIGHTS = ROOT / "static" / "data" / "operational_console_insights.json"
ROLE_VIEWS = ROOT / "static" / "data" / "operational_console_role_views.json"
EXPORT_DIR = ROOT / "static" / "data" / "exports"
REPORT = ROOT / "reports" / "operational_console_enhancement_suite_status.json"


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


def site_rows(registry: dict) -> list[dict]:
    rows = []
    for site in registry.get("sites", []) if isinstance(registry, dict) else []:
        if not isinstance(site, dict):
            continue
        key = site.get("site_key") or site.get("key") or site.get("site")
        classification = site.get("classification") or ("monitored" if site.get("is_monitored") else "discovered")
        risk_score = 0
        reasons = []
        if classification != "monitored":
            risk_score += 20
            reasons.append("not monitored")
        if site.get("is_monitored") is False:
            risk_score += 10
            reasons.append("monitoring disabled")
        rows.append({
            "site_key": key,
            "classification": classification,
            "is_monitored": site.get("is_monitored"),
            "cloud_id": site.get("cloud_id"),
            "url": site.get("url") or site.get("site_url"),
            "risk_score": risk_score,
            "risk_band": "low" if risk_score < 25 else "review",
            "risk_reasons": reasons,
        })
    return rows


def footprint_rows(footprint: dict) -> list[dict]:
    candidates = footprint.get("users") if isinstance(footprint, dict) else []
    if isinstance(candidates, list):
        return candidates[:1000]
    if isinstance(footprint.get("user_rows"), list):
        return footprint.get("user_rows")[:1000]
    return []


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for row in rows for k in row.keys()}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def main() -> int:
    registry = read_json(ROOT / "static" / "data" / "site_registry.json") or {}
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    runtime = read_json(ROOT / "static" / "data" / "runtime_refresh_status.json") or {}
    ui_view = read_json(ROOT / "static" / "data" / "operational_console_ui_view.json") or {}
    drilldowns = read_json(ROOT / "static" / "data" / "operational_console_drilldowns.json") or {}
    footprint = read_json(ROOT / "static" / "data" / "user_footprint.json") or {}

    sites = site_rows(registry)
    users = footprint_rows(footprint)
    advisories = reliability.get("advisories") or []
    issues = reliability.get("issues") or []

    monitored = [s for s in sites if s.get("classification") == "monitored" or s.get("is_monitored") is True]
    discovered = [s for s in sites if s not in monitored]
    risk_total = sum(s.get("risk_score") or 0 for s in sites) + len(issues) * 50 + len(advisories) * 5

    insights = {
        "schema": "jom-operational-console-insights-v1",
        "generated_at_utc": now_utc(),
        "overall_status": ui_view.get("overall_status"),
        "summary": {
            "site_count": len(sites),
            "monitored_site_count": len(monitored),
            "discovered_site_count": len(discovered),
            "issue_count": len(issues),
            "advisory_count": len(advisories),
            "operator_risk_score": risk_total,
            "operator_risk_band": "ok" if risk_total < 25 else "review" if risk_total < 75 else "attention",
        },
        "filters": {
            "site_classifications": sorted(set(s.get("classification") for s in sites if s.get("classification"))),
            "risk_bands": sorted(set(s.get("risk_band") for s in sites if s.get("risk_band"))),
        },
        "tables": {
            "sites": sites,
            "advisories": advisories,
            "issues": issues,
            "users_sample": users[:250],
        },
        "exports": {
            "sites_csv": "/static/data/exports/operational_console_sites.csv",
            "advisories_csv": "/static/data/exports/operational_console_advisories.csv",
            "users_sample_csv": "/static/data/exports/operational_console_users_sample.csv",
        },
        "source_refs": {
            "ui_view": "static/data/operational_console_ui_view.json",
            "drilldowns": "static/data/operational_console_drilldowns.json",
            "source_reliability": "static/data/source_reliability_status.json",
            "runtime_refresh": "static/data/runtime_refresh_status.json",
        },
    }

    role_views = {
        "schema": "jom-operational-console-role-views-v1",
        "generated_at_utc": now_utc(),
        "mode": "ui-view-metadata-only-not-auth-enforcement",
        "roles": {
            "operator": {
                "label": "Operator",
                "visible_panels": ["scheduler", "source_reliability", "runtime_refresh", "site_registry", "user_footprint"],
                "default_filter": "all",
            },
            "manager": {
                "label": "Manager",
                "visible_panels": ["source_reliability", "site_registry", "advisories"],
                "default_filter": "summary",
            },
            "governance": {
                "label": "Governance",
                "visible_panels": ["source_reliability", "advisories", "site_registry", "named_access"],
                "default_filter": "review",
            },
        },
        "security_note": "This file only controls UI presentation. It is not authentication or authorization enforcement.",
    }

    write_json(INSIGHTS, insights)
    write_json(ROLE_VIEWS, role_views)
    write_csv(EXPORT_DIR / "operational_console_sites.csv", sites)
    write_csv(EXPORT_DIR / "operational_console_advisories.csv", advisories)
    write_csv(EXPORT_DIR / "operational_console_users_sample.csv", users[:250])

    report = {
        "schema": "jom-operational-console-enhancement-suite-v1-status",
        "generated_at_utc": now_utc(),
        "status": "ok",
        "outputs": [str(INSIGHTS), str(ROLE_VIEWS)],
        "exports": list(insights["exports"].values()),
        "summary": insights["summary"],
        "note": "Role views are UI metadata only and do not enforce access control.",
    }
    write_json(REPORT, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
