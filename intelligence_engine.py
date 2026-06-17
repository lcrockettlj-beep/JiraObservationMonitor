# intelligence_engine.py


def safe_int(val):
    try:
        return int(val)
    except Exception:
        return 0



def enrich_site(site):
    site = site if isinstance(site, dict) else {}

    issues_total = safe_int(site.get("issue_count_total"))
    issues_updated = safe_int(site.get("issue_count_updated_last_7d"))

    if issues_total == 0 and issues_updated == 0:
        activity_status = "inactive"
    elif issues_updated == 0:
        activity_status = "stalled"
    else:
        activity_status = "active"

    site["activity_status"] = activity_status

    if activity_status == "inactive":
        activity_risk = "high"
    elif activity_status == "stalled":
        activity_risk = "medium"
    else:
        activity_risk = "low"

    site["activity_risk"] = activity_risk

    signals = []
    if issues_total == 0:
        signals.append("no_issues_detected")
    if issues_updated == 0:
        signals.append("no_recent_activity")
    if safe_int(site.get("project_count")) > 30:
        signals.append("large_project_footprint")

    site["intelligence_signals"] = signals

    score = 0
    if activity_risk == "high":
        score += 3
    elif activity_risk == "medium":
        score += 2
    else:
        score += 1

    site["intelligence_score"] = score
    return site



def enrich_estate(data):
    data = data if isinstance(data, dict) else {}
    sites = data.get("sites", []) if isinstance(data.get("sites", []), list) else []

    enriched = []
    total_projects = 0
    total_issues = 0
    active_sites = 0

    for site in sites:
        if not isinstance(site, dict):
            continue
        site = enrich_site(site)
        total_projects += safe_int(site.get("project_count"))
        total_issues += safe_int(site.get("issue_count_total"))
        if site.get("activity_status") == "active":
            active_sites += 1
        enriched.append(site)

    data["intelligence_summary"] = {
        "total_sites": len(enriched),
        "total_projects": total_projects,
        "total_issues": total_issues,
        "active_sites": active_sites,
        "inactive_sites": len(enriched) - active_sites,
    }
    data["sites"] = enriched
    return data
