def determine_site_status(site_record):
    api_checks = site_record.get("api_checks", {})
    api_errors = site_record.get("api_errors", {})

    blocking_failed_checks = []
    permission_limited_checks = []

    for check_name, ok in api_checks.items():
        if ok:
            continue

        error_text = (api_errors.get(check_name) or "").lower()

        # Treat application_roles 403 as permission-limited, not site health failure
        if check_name == "application_roles" and "403" in error_text:
            permission_limited_checks.append(check_name)
            continue

        blocking_failed_checks.append(check_name)

    blocking_failure_count = len(blocking_failed_checks)

    if blocking_failure_count >= 2:
        status = "critical"
    elif blocking_failure_count == 1:
        status = "warning"
    else:
        status = "healthy"

    return {
        "status": status,
        "blocking_failed_checks": blocking_failed_checks,
        "blocking_failure_count": blocking_failure_count,
        "permission_limited_checks": permission_limited_checks
    }


def enrich_collection(raw_collection):
    sites = raw_collection.get("sites", [])

    enriched_sites = []
    healthy_count = 0
    warning_count = 0
    critical_count = 0

    for site in sites:
        status_result = determine_site_status(site)

        enriched_site = dict(site)
        enriched_site["status"] = status_result["status"]
        enriched_site["failed_api_checks"] = status_result["blocking_failure_count"]
        enriched_site["blocking_failed_checks"] = status_result["blocking_failed_checks"]
        enriched_site["permission_limited_checks"] = status_result["permission_limited_checks"]

        if status_result["status"] == "healthy":
            healthy_count += 1
        elif status_result["status"] == "warning":
            warning_count += 1
        else:
            critical_count += 1

        enriched_sites.append(enriched_site)

    return {
        "site_count": len(enriched_sites),
        "healthy_count": healthy_count,
        "warning_count": warning_count,
        "critical_count": critical_count,
        "sites": enriched_sites
    }