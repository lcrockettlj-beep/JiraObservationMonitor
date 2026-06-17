"""
backend/intelligence_engine.py

Step 3.1 – Operational Intelligence Engine
------------------------------------------
Additive, backend-only module for read-only risk detection and drilldown payloads.

Design goals:
- Safe: no network calls, no writes, no destructive actions
- Additive: can be imported without changing existing collectors
- Flexible: accepts partially-complete payloads from CSV or API collectors
- Read-only operational console outputs with reasons + next-action links

Expected rough input shape (keys are optional):
{
    "generated_at": "2026-06-17T13:00:00Z",
    "sites": [
        {
            "id": "site-1",
            "name": "GLI Global Technology",
            "url": "https://example.atlassian.net",
            "license_model": "seat-paid" | "tiered",
            "billing": {
                "seats_used": 120,
                "seat_limit": 150,
                "tier_used": 450,
                "tier_limit": 500
            },
            "users": [
                {
                    "account_id": "abc",
                    "display_name": "Jane Doe",
                    "email": "jane@example.com",
                    "managed": true,
                    "disabled": false,
                    "active": true,
                    "days_inactive": 92,
                    "products": ["Jira", "Confluence"]
                }
            ],
            "projects": [
                {
                    "key": "OPS",
                    "name": "Operations",
                    "archived": false,
                    "lead": "Jane Doe",
                    "days_since_activity": 140
                }
            ],
            "apps": [
                {
                    "key": "tempo",
                    "name": "Tempo Timesheets",
                    "enabled": true,
                    "last_used_days": 120
                }
            ]
        }
    ]
}
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Iterable
from statistics import mean


DEFAULT_THRESHOLDS = {
    "inactive_days_user": 90,
    "inactive_days_project": 120,
    "inactive_days_app": 90,
    "tier_warning_ratio": 0.85,
    "tier_critical_ratio": 0.95,
    "seat_warning_ratio": 0.85,
    "seat_critical_ratio": 0.95,
}


@dataclass
class RiskFlag:
    type: str
    severity: str
    count: int
    reason: str
    action: str
    details: Optional[Dict[str, Any]] = None


def _as_list(value: Any) -> List[dict]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def _safe_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _safe_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _safe_num(value: Any, default: float = 0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _round_num(value: float) -> float:
    return round(float(value), 2)


def _severity_from_ratio(ratio: float, warning: float, critical: float) -> Optional[str]:
    if ratio >= critical:
        return "critical"
    if ratio >= warning:
        return "warning"
    return None


def _score_for_severity(severity: str, count: int = 1) -> int:
    mult = {
        "info": 2,
        "warning": 6,
        "critical": 12,
    }.get(severity, 0)
    return mult * max(count, 1)


def _risk_category(score: int) -> str:
    if score >= 60:
        return "Critical"
    if score >= 25:
        return "Warning"
    return "Healthy"


def _site_detail_url(site: Dict[str, Any], slug: str) -> str:
    site_id = _safe_str(site.get("id")) or _safe_str(site.get("name"), "site")
    site_id = site_id.replace(" ", "-").lower()
    return f"/detail/{slug}::site::{site_id}"


def _detect_inactive_users(site: Dict[str, Any], thresholds: Dict[str, float]) -> Optional[RiskFlag]:
    users = _as_list(site.get("users"))
    flagged = []
    cutoff = thresholds["inactive_days_user"]
    for u in users:
        active = _safe_bool(u.get("active"), True)
        disabled = _safe_bool(u.get("disabled"), False)
        days_inactive = _safe_num(u.get("days_inactive"), 0)
        products = u.get("products") if isinstance(u.get("products"), list) else []
        if (disabled or active) and days_inactive >= cutoff and len(products) > 0:
            flagged.append({
                "account_id": u.get("account_id"),
                "display_name": u.get("display_name"),
                "email": u.get("email"),
                "days_inactive": int(days_inactive),
                "disabled": disabled,
                "products": products,
                "reason": f"Inactive for {int(days_inactive)} days but still has product access",
            })
    if not flagged:
        return None
    return RiskFlag(
        type="inactive_users",
        severity="warning" if len(flagged) < 10 else "critical",
        count=len(flagged),
        reason=f"Users inactive for {int(cutoff)}+ days still have product access.",
        action=_site_detail_url(site, "users-inactive"),
        details={"items": flagged},
    )


def _detect_unmanaged_accounts(site: Dict[str, Any]) -> Optional[RiskFlag]:
    users = _as_list(site.get("users"))
    flagged = []
    for u in users:
        products = u.get("products") if isinstance(u.get("products"), list) else []
        managed = _safe_bool(u.get("managed"), False)
        if (not managed) and len(products) > 0:
            flagged.append({
                "account_id": u.get("account_id"),
                "display_name": u.get("display_name"),
                "email": u.get("email"),
                "products": products,
                "reason": "Unmanaged account still has site/product access",
            })
    if not flagged:
        return None
    return RiskFlag(
        type="unmanaged_accounts",
        severity="warning",
        count=len(flagged),
        reason="Unmanaged accounts still hold site or product access.",
        action=_site_detail_url(site, "accounts-unmanaged"),
        details={"items": flagged},
    )


def _detect_orphaned_projects(site: Dict[str, Any], thresholds: Dict[str, float]) -> Optional[RiskFlag]:
    projects = _as_list(site.get("projects"))
    cutoff = thresholds["inactive_days_project"]
    flagged = []
    for p in projects:
        archived = _safe_bool(p.get("archived"), False)
        days = _safe_num(p.get("days_since_activity"), 0)
        if not archived and days >= cutoff:
            flagged.append({
                "key": p.get("key"),
                "name": p.get("name"),
                "lead": p.get("lead"),
                "days_since_activity": int(days),
                "reason": f"No recent activity for {int(days)} days",
            })
    if not flagged:
        return None
    return RiskFlag(
        type="orphaned_projects",
        severity="warning" if len(flagged) < 5 else "critical",
        count=len(flagged),
        reason=f"Projects with no recent activity for {int(cutoff)}+ days.",
        action=_site_detail_url(site, "projects-orphaned"),
        details={"items": flagged},
    )


def _detect_unused_apps(site: Dict[str, Any], thresholds: Dict[str, float]) -> Optional[RiskFlag]:
    apps = _as_list(site.get("apps"))
    cutoff = thresholds["inactive_days_app"]
    flagged = []
    for a in apps:
        enabled = _safe_bool(a.get("enabled"), True)
        last_used_days = _safe_num(a.get("last_used_days"), 0)
        if enabled and last_used_days >= cutoff:
            flagged.append({
                "key": a.get("key"),
                "name": a.get("name"),
                "last_used_days": int(last_used_days),
                "reason": f"Enabled app appears unused for {int(last_used_days)} days",
            })
    if not flagged:
        return None
    return RiskFlag(
        type="unused_apps",
        severity="warning",
        count=len(flagged),
        reason=f"Installed apps enabled but not recently used ({int(cutoff)}+ days).",
        action=_site_detail_url(site, "apps-unused"),
        details={"items": flagged},
    )


def _detect_capacity(site: Dict[str, Any], thresholds: Dict[str, float]) -> Optional[RiskFlag]:
    billing = site.get("billing") if isinstance(site.get("billing"), dict) else {}
    license_model = _safe_str(site.get("license_model"), "")

    if license_model == "tiered":
        used = _safe_num(billing.get("tier_used"), 0)
        limit = _safe_num(billing.get("tier_limit"), 0)
        if limit <= 0:
            return None
        ratio = used / limit
        sev = _severity_from_ratio(ratio, thresholds["tier_warning_ratio"], thresholds["tier_critical_ratio"])
        if not sev:
            return None
        return RiskFlag(
            type="tier_capacity",
            severity=sev,
            count=1,
            reason=f"Tier usage at {_round_num(ratio * 100)}% ({int(used)}/{int(limit)}).",
            action=_site_detail_url(site, "billing-capacity"),
            details={"used": used, "limit": limit, "ratio": ratio, "license_model": license_model},
        )

    if license_model == "seat-paid":
        used = _safe_num(billing.get("seats_used"), 0)
        limit = _safe_num(billing.get("seat_limit"), 0)
        if limit <= 0:
            return None
        ratio = used / limit
        sev = _severity_from_ratio(ratio, thresholds["seat_warning_ratio"], thresholds["seat_critical_ratio"])
        if not sev:
            return None
        return RiskFlag(
            type="seat_capacity",
            severity=sev,
            count=1,
            reason=f"Seat usage at {_round_num(ratio * 100)}% ({int(used)}/{int(limit)}).",
            action=_site_detail_url(site, "billing-capacity"),
            details={"used": used, "limit": limit, "ratio": ratio, "license_model": license_model},
        )
    return None


def analyze_site(site: Dict[str, Any], thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    risks: List[RiskFlag] = []
    for detector in (
        lambda s: _detect_inactive_users(s, thresholds),
        _detect_unmanaged_accounts,
        lambda s: _detect_orphaned_projects(s, thresholds),
        lambda s: _detect_unused_apps(s, thresholds),
        lambda s: _detect_capacity(s, thresholds),
    ):
        result = detector(site)
        if result:
            risks.append(result)

    score = sum(_score_for_severity(r.severity, r.count) for r in risks)
    users = _as_list(site.get("users"))
    projects = _as_list(site.get("projects"))
    apps = _as_list(site.get("apps"))

    summary = {
        "id": site.get("id") or site.get("name"),
        "name": site.get("name"),
        "url": site.get("url"),
        "license_model": site.get("license_model"),
        "risk_score": score,
        "risk_category": _risk_category(score),
        "risk_count": len(risks),
        "users_count": len(users),
        "projects_count": len(projects),
        "apps_count": len(apps),
        "why_it_stands_out": [r.reason for r in risks[:3]],
        "risks": [asdict(r) for r in risks],
    }
    return summary


def build_intelligence_snapshot(source: Dict[str, Any], thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    sites = _as_list(source.get("sites"))
    analyzed = [analyze_site(site, thresholds=thresholds) for site in sites]

    estate_score = int(sum(s.get("risk_score", 0) for s in analyzed))
    all_risks = [risk for site in analyzed for risk in site.get("risks", [])]
    avg_site_score = _round_num(mean([s.get("risk_score", 0) for s in analyzed]) if analyzed else 0)

    top_risks = sorted(
        all_risks,
        key=lambda r: (
            {"critical": 3, "warning": 2, "info": 1}.get(r.get("severity", "info"), 0),
            r.get("count", 0),
        ),
        reverse=True,
    )[:10]

    snapshot = {
        "generated_at": source.get("generated_at"),
        "estate": {
            "sites_count": len(analyzed),
            "estate_risk_score": estate_score,
            "average_site_risk_score": avg_site_score,
            "top_risks": top_risks,
            "risk_category": _risk_category(estate_score),
        },
        "sites": analyzed,
        "thresholds": thresholds,
    }
    return snapshot


def attach_intelligence(source: Dict[str, Any], thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Non-destructive helper.
    Returns a shallow copy of source with `intelligence` attached.
    """
    output = dict(source or {})
    output["intelligence"] = build_intelligence_snapshot(source or {}, thresholds=thresholds)
    return output
