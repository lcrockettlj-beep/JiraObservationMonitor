def _safe_int(value, default=0):
    if isinstance(value, int):
        return value
    return default


def _safe_float(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _safe_divide(numerator, denominator):
    if denominator <= 0:
        return 0.0
    return numerator / denominator


CORE_ENDPOINT_KEYS = {
    "server_info",
    "myself",
    "projects"
}


def _classify_api_failures(site_record):
    endpoint_summary = site_record.get("endpoint_summary", {}) or {}

    core_blocking_failed_checks = endpoint_summary.get("core_blocking_failed_checks", []) or []
    enrichment_failed_checks = endpoint_summary.get("enrichment_failed_checks", []) or []
    permission_limited_checks = endpoint_summary.get("permission_limited_checks", []) or []
    failed_check_details = endpoint_summary.get("failed_check_details", []) or []

    transient_failed_checks = []
    hard_failed_checks = []

    for detail in failed_check_details:
        endpoint_key = detail.get("endpoint_key")
        endpoint_type = detail.get("endpoint_type")
        error_category = detail.get("error_category")
        permission_limited = detail.get("permission_limited", False)

        if permission_limited:
            continue

        if endpoint_type != "core":
            continue

        if error_category in {"timeout", "connection_error", "rate_limited", "server_error", "transient_error"}:
            transient_failed_checks.append(endpoint_key)
        else:
            hard_failed_checks.append(endpoint_key)

    return {
        "core_blocking_failed_checks": core_blocking_failed_checks,
        "enrichment_failed_checks": enrichment_failed_checks,
        "permission_limited_checks": permission_limited_checks,
        "transient_failed_checks": sorted(set(transient_failed_checks)),
        "hard_failed_checks": sorted(set(hard_failed_checks))
    }


def _build_issue_signals(site_record):
    total_issues = _safe_int(site_record.get("issue_count_total", 0))
    unresolved_issues = _safe_int(site_record.get("issue_count_unresolved", 0))
    updated_last_7d = _safe_int(site_record.get("issue_count_updated_last_7d", 0))
    project_count = _safe_int(site_record.get("project_count", 0))

    unresolved_ratio = _safe_divide(unresolved_issues, total_issues)
    issues_per_project = _safe_divide(total_issues, project_count) if project_count > 0 else 0.0
    unresolved_per_project = _safe_divide(unresolved_issues, project_count) if project_count > 0 else 0.0

    signals = []
    score = 0

    if unresolved_issues >= 250:
        score += 4
        signals.append("extreme_unresolved_volume")
    elif unresolved_issues >= 100:
        score += 3
        signals.append("very_high_unresolved_volume")
    elif unresolved_issues >= 40:
        score += 2
        signals.append("high_unresolved_volume")
    elif unresolved_issues >= 15:
        score += 1
        signals.append("moderate_unresolved_volume")

    if total_issues >= 20:
        if unresolved_ratio >= 0.70:
            score += 4
            signals.append("extreme_unresolved_ratio")
        elif unresolved_ratio >= 0.50:
            score += 3
            signals.append("very_high_unresolved_ratio")
        elif unresolved_ratio >= 0.35:
            score += 2
            signals.append("high_unresolved_ratio")
        elif unresolved_ratio >= 0.20:
            score += 1
            signals.append("moderate_unresolved_ratio")

    if total_issues >= 2000:
        score += 3
        signals.append("extreme_total_issue_volume")
    elif total_issues >= 1000:
        score += 2
        signals.append("very_high_total_issue_volume")
    elif total_issues >= 300:
        score += 1
        signals.append("high_total_issue_volume")

    if project_count > 0:
        if issues_per_project >= 200:
            score += 3
            signals.append("extreme_issues_per_project")
        elif issues_per_project >= 100:
            score += 2
            signals.append("very_high_issues_per_project")
        elif issues_per_project >= 60:
            score += 1
            signals.append("high_issues_per_project")

        if unresolved_per_project >= 30:
            score += 3
            signals.append("extreme_unresolved_per_project")
        elif unresolved_per_project >= 15:
            score += 2
            signals.append("very_high_unresolved_per_project")
        elif unresolved_per_project >= 8:
            score += 1
            signals.append("high_unresolved_per_project")

    if unresolved_issues >= 15 and updated_last_7d <= 3:
        score += 2
        signals.append("low_recent_activity_with_backlog")
    elif total_issues >= 50 and updated_last_7d == 0:
        score += 1
        signals.append("no_recent_activity")

    return {
        "unresolved_ratio": round(unresolved_ratio, 4),
        "issues_per_project": round(issues_per_project, 2),
        "unresolved_per_project": round(unresolved_per_project, 2),
        "issue_risk_score": score,
        "issue_risk_signals": signals
    }


def _build_operational_signals(site_record):
    signals = []
    score = 0

    collection_duration_seconds = _safe_float(site_record.get("collection_duration_seconds", 0))
    endpoint_summary = site_record.get("endpoint_summary", {}) or {}

    total_checks = _safe_int(endpoint_summary.get("total_checks", 0))
    failed_checks = _safe_int(endpoint_summary.get("failed_checks", 0))
    core_blocking_count = len(endpoint_summary.get("core_blocking_failed_checks", []) or [])
    enrichment_failed_count = len(endpoint_summary.get("enrichment_failed_checks", []) or [])
    permission_limited_count = len(endpoint_summary.get("permission_limited_checks", []) or [])

    failed_ratio = _safe_divide(failed_checks, total_checks)

    if collection_duration_seconds >= 10:
        score += 2
        signals.append("slow_collection")
    elif collection_duration_seconds >= 5:
        score += 1
        signals.append("elevated_collection_time")

    if core_blocking_count >= 2:
        score += 3
        signals.append("multiple_core_endpoint_failures")
    elif core_blocking_count == 1:
        score += 2
        signals.append("single_core_endpoint_failure")

    if enrichment_failed_count >= 3:
        score += 2
        signals.append("multiple_enrichment_failures")
    elif enrichment_failed_count >= 1:
        score += 1
        signals.append("some_enrichment_failures")

    if permission_limited_count >= 2:
        score += 1
        signals.append("multiple_permission_limited_endpoints")

    if total_checks >= 4:
        if failed_ratio >= 0.50:
            score += 2
            signals.append("high_endpoint_failure_ratio")
        elif failed_ratio >= 0.25:
            score += 1
            signals.append("moderate_endpoint_failure_ratio")

    return {
        "operational_risk_score": score,
        "operational_risk_signals": signals,
        "collection_duration_seconds": collection_duration_seconds,
        "endpoint_failure_ratio": round(failed_ratio, 4)
    }


def _determine_status(hard_core_failures, transient_core_failures, issue_risk_score, operational_risk_score):
    # Hard core failures matter most
    if hard_core_failures >= 2:
        return "critical"

    if hard_core_failures == 1:
        return "warning"

    # Multiple transient core failures still matter
    if transient_core_failures >= 2:
        return "warning"

    if issue_risk_score + operational_risk_score >= 8:
        return "warning"

    return "healthy"


def _build_status_reasons(core_blocking_failed_checks, enrichment_failed_checks, permission_limited_checks, issue_signals, operational_signals):
    reasons = []

    if core_blocking_failed_checks:
        reasons.append(f"core_failures={','.join(core_blocking_failed_checks)}")

    if enrichment_failed_checks:
        reasons.append(f"enrichment_failures={','.join(enrichment_failed_checks)}")

    if permission_limited_checks:
        reasons.append(f"permission_limited={','.join(permission_limited_checks)}")

    for signal in issue_signals:
        reasons.append(f"issue_signal={signal}")

    for signal in operational_signals:
        reasons.append(f"operational_signal={signal}")

    if not reasons:
        reasons.append("no_risk_signals_detected")

    return reasons


def determine_site_status(site_record):
    api_failure_result = _classify_api_failures(site_record)

    core_blocking_failed_checks = api_failure_result["core_blocking_failed_checks"]
    enrichment_failed_checks = api_failure_result["enrichment_failed_checks"]
    permission_limited_checks = api_failure_result["permission_limited_checks"]
    transient_failed_checks = api_failure_result["transient_failed_checks"]
    hard_failed_checks = api_failure_result["hard_failed_checks"]

    issue_result = _build_issue_signals(site_record)
    operational_result = _build_operational_signals(site_record)

    hard_core_failure_count = len(hard_failed_checks)
    transient_core_failure_count = len(transient_failed_checks)

    status = _determine_status(
        hard_core_failures=hard_core_failure_count,
        transient_core_failures=transient_core_failure_count,
        issue_risk_score=issue_result["issue_risk_score"],
        operational_risk_score=operational_result["operational_risk_score"]
    )

    risk_score = (
        (hard_core_failure_count * 6)
        + (transient_core_failure_count * 3)
        + issue_result["issue_risk_score"]
        + operational_result["operational_risk_score"]
        + len(permission_limited_checks)
    )

    status_reasons = _build_status_reasons(
        core_blocking_failed_checks=core_blocking_failed_checks,
        enrichment_failed_checks=enrichment_failed_checks,
        permission_limited_checks=permission_limited_checks,
        issue_signals=issue_result["issue_risk_signals"],
        operational_signals=operational_result["operational_risk_signals"]
    )

    return {
        "status": status,
        "risk_score": risk_score,
        "failed_api_checks": hard_core_failure_count + transient_core_failure_count,
        "blocking_failed_checks": core_blocking_failed_checks,
        "enrichment_failed_checks": enrichment_failed_checks,
        "permission_limited_checks": permission_limited_checks,
        "transient_failed_checks": transient_failed_checks,
        "hard_failed_checks": hard_failed_checks,
        "status_reasons": status_reasons,
        "issue_metrics": {
            "unresolved_ratio": issue_result["unresolved_ratio"],
            "issues_per_project": issue_result["issues_per_project"],
            "unresolved_per_project": issue_result["unresolved_per_project"]
        },
        "issue_risk_score": issue_result["issue_risk_score"],
        "issue_risk_signals": issue_result["issue_risk_signals"],
        "operational_risk_score": operational_result["operational_risk_score"],
        "operational_risk_signals": operational_result["operational_risk_signals"],
        "site_health_breakdown": {
            "hard_core_failure_count": hard_core_failure_count,
            "transient_core_failure_count": transient_core_failure_count,
            "enrichment_failure_count": len(enrichment_failed_checks),
            "permission_limited_count": len(permission_limited_checks),
            "collection_duration_seconds": operational_result["collection_duration_seconds"],
            "endpoint_failure_ratio": operational_result["endpoint_failure_ratio"]
        }
    }


def enrich_collection(raw_collection):
    sites = raw_collection.get("sites", [])

    enriched_sites = []
    healthy_count = 0
    warning_count = 0
    critical_count = 0

    total_risk_score = 0
    total_blocking_failures = 0
    total_permission_limited_checks = 0
    total_issue_risk_score = 0
    total_operational_risk_score = 0

    for site in sites:
        status_result = determine_site_status(site)

        enriched_site = dict(site)
        enriched_site["status"] = status_result["status"]
        enriched_site["risk_score"] = status_result["risk_score"]
        enriched_site["failed_api_checks"] = status_result["failed_api_checks"]
        enriched_site["blocking_failed_checks"] = status_result["blocking_failed_checks"]
        enriched_site["enrichment_failed_checks"] = status_result["enrichment_failed_checks"]
        enriched_site["permission_limited_checks"] = status_result["permission_limited_checks"]
        enriched_site["transient_failed_checks"] = status_result["transient_failed_checks"]
        enriched_site["hard_failed_checks"] = status_result["hard_failed_checks"]
        enriched_site["status_reasons"] = status_result["status_reasons"]
        enriched_site["issue_metrics"] = status_result["issue_metrics"]
        enriched_site["issue_risk_score"] = status_result["issue_risk_score"]
        enriched_site["issue_risk_signals"] = status_result["issue_risk_signals"]
        enriched_site["operational_risk_score"] = status_result["operational_risk_score"]
        enriched_site["operational_risk_signals"] = status_result["operational_risk_signals"]
        enriched_site["site_health_breakdown"] = status_result["site_health_breakdown"]

        total_risk_score += status_result["risk_score"]
        total_blocking_failures += status_result["failed_api_checks"]
        total_permission_limited_checks += len(status_result["permission_limited_checks"])
        total_issue_risk_score += status_result["issue_risk_score"]
        total_operational_risk_score += status_result["operational_risk_score"]

        if status_result["status"] == "healthy":
            healthy_count += 1
        elif status_result["status"] == "warning":
            warning_count += 1
        else:
            critical_count += 1

        enriched_sites.append(enriched_site)

    enriched_sites.sort(
        key=lambda site: (
            0 if site.get("status") == "critical" else
            1 if site.get("status") == "warning" else
            2,
            -site.get("risk_score", 0),
            site.get("name", "")
        )
    )

    site_count = len(enriched_sites)
    average_risk_score = round(_safe_divide(total_risk_score, site_count), 2) if site_count > 0 else 0.0

    return {
        "site_count": site_count,
        "healthy_count": healthy_count,
        "warning_count": warning_count,
        "critical_count": critical_count,
        "total_risk_score": total_risk_score,
        "average_risk_score": average_risk_score,
        "total_blocking_failures": total_blocking_failures,
        "total_permission_limited_checks": total_permission_limited_checks,
        "total_issue_risk_score": total_issue_risk_score,
        "total_operational_risk_score": total_operational_risk_score,
        "sites": enriched_sites
    }