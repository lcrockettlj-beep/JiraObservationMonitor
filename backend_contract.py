def _safe_int(value, default=0):
    if isinstance(value, int):
        return value
    return default


def _site_status_group(status):
    if status == "critical":
        return "critical"
    if status == "warning":
        return "warning"
    return "operationally_stable"


def _licence_panel(site):
    licence_summary = site.get("licence_summary", {}) or {}

    return {
        "status": site.get("licence_status"),
        "api_access": site.get("licence_api_access"),
        "licensed_users_estimate": licence_summary.get("licensed_users_estimate"),
        "products": licence_summary.get("products", []) or []
    }


def _usage_growth_panel(site):
    user_summary = site.get("user_summary", {}) or {}

    return {
        "total_projects": site.get("project_count", 0),
        "project_delta": site.get("project_count_delta"),
        "total_users": user_summary.get("total_users"),
        "total_users_delta": site.get("total_users_delta"),
        "active_users": user_summary.get("active_users"),
        "active_users_delta": site.get("active_users_delta"),
        "inactive_users": user_summary.get("inactive_users"),
        "inactive_users_delta": site.get("inactive_users_delta"),
        "licensed_users_estimate": (site.get("licence_summary", {}) or {}).get("licensed_users_estimate"),
        "licensed_users_estimate_delta": site.get("licensed_users_estimate_delta"),
        "growth_status": site.get("growth_status")
    }


def _operations_panel(site):
    audit_summary = site.get("audit_summary", {}) or {}
    automation_summary = site.get("automation_summary", {}) or {}

    return {
        "audit_status": site.get("audit_status"),
        "audit_api_access": site.get("audit_api_access"),
        "audit_record_count": audit_summary.get("record_count"),
        "automation_related_audit_record_count": audit_summary.get("automation_related_record_count"),
        "automation_api_supported": automation_summary.get("rule_management_supported_with_current_auth"),
        "automation_note": automation_summary.get("reason"),
        "permission_limited_checks": site.get("permission_limited_checks", []) or []
    }


def _projects_panel(site):
    return {
        "project_count": site.get("project_count", 0),
        "project_sample": site.get("project_sample", []) or []
    }


def _issues_panel(site):
    return {
        "issue_count_total": site.get("issue_count_total", 0),
        "issue_count_total_delta": site.get("issue_count_total_delta"),
        "issue_count_unresolved": site.get("issue_count_unresolved", 0),
        "issue_count_unresolved_delta": site.get("issue_count_unresolved_delta"),
        "issue_count_updated_last_7d": site.get("issue_count_updated_last_7d", 0)
    }


def build_site_contract(site):
    return {
        "site_identity": {
            "name": site.get("name"),
            "url": site.get("url"),
            "cloud_id": site.get("cloud_id")
        },
        "health": {
            "status": site.get("status"),
            "risk_score": site.get("risk_score", 0),
            "status_reasons": site.get("status_reasons", []) or [],
            "permission_limited_checks": site.get("permission_limited_checks", []) or []
        },
        "usage_growth_panel": _usage_growth_panel(site),
        "licence_panel": _licence_panel(site),
        "operations_panel": _operations_panel(site),
        "issues_panel": _issues_panel(site),
        "projects_panel": _projects_panel(site),
        "raw_backend_flags": {
            "snapshot_baseline": site.get("snapshot_baseline"),
            "audit_status": site.get("audit_status"),
            "audit_api_access": site.get("audit_api_access"),
            "licence_status": site.get("licence_status"),
            "licence_api_access": site.get("licence_api_access")
        }
    }


def build_homepage_contract(enriched_collection, raw_collection=None):
    sites = enriched_collection.get("sites", []) or []

    cards = []
    for site in sites:
        user_summary = site.get("user_summary", {}) or {}
        licence_summary = site.get("licence_summary", {}) or {}

        cards.append({
            "name": site.get("name"),
            "url": site.get("url"),
            "status": site.get("status"),
            "status_group": _site_status_group(site.get("status")),
            "risk_score": site.get("risk_score", 0),
            "project_count": site.get("project_count", 0),
            "project_delta": site.get("project_count_delta"),
            "total_users": user_summary.get("total_users"),
            "total_users_delta": site.get("total_users_delta"),
            "active_users": user_summary.get("active_users"),
            "inactive_users": user_summary.get("inactive_users"),
            "licensed_users_estimate": licence_summary.get("licensed_users_estimate"),
            "licensed_users_estimate_delta": site.get("licensed_users_estimate_delta"),
            "growth_status": site.get("growth_status"),
            "audit_status": site.get("audit_status"),
            "audit_api_access": site.get("audit_api_access"),
            "licence_status": site.get("licence_status"),
            "licence_api_access": site.get("licence_api_access"),
            "permission_limited_checks": site.get("permission_limited_checks", []) or [],
            "status_reasons": site.get("status_reasons", []) or []
        })

    cards.sort(
        key=lambda item: (
            0 if item.get("status_group") == "critical" else
            1 if item.get("status_group") == "warning" else
            2,
            -_safe_int(item.get("risk_score", 0), 0),
            item.get("name", "")
        )
    )

    summary_strip = {
        "site_count": enriched_collection.get("site_count", 0),
        "healthy_count": enriched_collection.get("healthy_count", 0),
        "warning_count": enriched_collection.get("warning_count", 0),
        "critical_count": enriched_collection.get("critical_count", 0),
        "total_risk_score": enriched_collection.get("total_risk_score", 0),
        "average_risk_score": enriched_collection.get("average_risk_score", 0),
        "project_delta_total": (enriched_collection.get("delta_summary", {}) or {}).get("project_delta_total"),
        "total_users_delta_total": (enriched_collection.get("delta_summary", {}) or {}).get("total_users_delta_total"),
        "licensed_users_estimate_delta_total": (enriched_collection.get("delta_summary", {}) or {}).get("licensed_users_estimate_delta_total")
    }

    excluded_sites = []
    if raw_collection:
        excluded_sites = raw_collection.get("excluded_sites", []) or []

    return {
        "summary_strip": summary_strip,
        "cards": cards,
        "excluded_sites": excluded_sites
    }


def build_ui_contract(raw_collection, enriched_collection):
    homepage = build_homepage_contract(enriched_collection, raw_collection=raw_collection)

    site_pages = {}
    for site in enriched_collection.get("sites", []) or []:
        site_pages[site.get("cloud_id")] = build_site_contract(site)

    return {
        "homepage": homepage,
        "site_pages": site_pages
    }