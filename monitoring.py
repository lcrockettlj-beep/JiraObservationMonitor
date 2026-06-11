def _safe_int(value, default=0):
    if isinstance(value, int):
        return value
    return default


def _build_site_lookup(snapshot):
    lookup = {}

    if not snapshot:
        return lookup

    for site in snapshot.get("sites", []):
        cloud_id = site.get("cloud_id")
        if cloud_id:
            lookup[cloud_id] = site

    return lookup


def _normalise_list(value):
    if not isinstance(value, list):
        return []
    return sorted([item for item in value if item is not None])


def _append_change(changes, change_type, site_name, cloud_id, field=None, old=None, new=None, severity="info"):
    change = {
        "type": change_type,
        "site_name": site_name,
        "cloud_id": cloud_id,
        "severity": severity
    }

    if field is not None:
        change["field"] = field

    if old is not None:
        change["old"] = old

    if new is not None:
        change["new"] = new

    changes.append(change)


def _site_metric(site, metric_name):
    user_summary = site.get("user_summary", {}) or {}
    licence_summary = site.get("licence_summary", {}) or {}

    if metric_name == "project_count":
        return _safe_int(site.get("project_count", 0))
    if metric_name == "issue_count_total":
        return _safe_int(site.get("issue_count_total", 0))
    if metric_name == "issue_count_unresolved":
        return _safe_int(site.get("issue_count_unresolved", 0))
    if metric_name == "issue_count_updated_last_7d":
        return _safe_int(site.get("issue_count_updated_last_7d", 0))
    if metric_name == "total_users":
        return _safe_int(user_summary.get("total_users", 0))
    if metric_name == "active_users":
        return _safe_int(user_summary.get("active_users", 0))
    if metric_name == "inactive_users":
        return _safe_int(user_summary.get("inactive_users", 0))
    if metric_name == "licensed_users_estimate":
        value = licence_summary.get("licensed_users_estimate")
        if isinstance(value, int):
            return value
        return 0

    return 0


def _compare_numeric_metric(changes, previous_site, current_site, metric_name, severity="info"):
    site_name = current_site.get("name")
    cloud_id = current_site.get("cloud_id")

    previous_value = _site_metric(previous_site, metric_name)
    current_value = _site_metric(current_site, metric_name)

    if previous_value != current_value:
        _append_change(
            changes=changes,
            change_type=f"{metric_name}_change",
            site_name=site_name,
            cloud_id=cloud_id,
            field=metric_name,
            old=previous_value,
            new=current_value,
            severity=severity
        )


def _compare_list_field(changes, site_name, cloud_id, field_name, previous_site, current_site, severity="info"):
    previous_value = _normalise_list(previous_site.get(field_name, []))
    current_value = _normalise_list(current_site.get(field_name, []))

    if previous_value != current_value:
        _append_change(
            changes=changes,
            change_type=f"{field_name}_change",
            site_name=site_name,
            cloud_id=cloud_id,
            field=field_name,
            old=previous_value,
            new=current_value,
            severity=severity
        )


def _compare_status(previous_site, current_site, changes):
    site_name = current_site.get("name")
    cloud_id = current_site.get("cloud_id")

    previous_status = previous_site.get("status")
    current_status = current_site.get("status")

    if previous_status != current_status:
        severity = "info"
        if current_status == "warning":
            severity = "warning"
        elif current_status == "critical":
            severity = "critical"

        _append_change(
            changes=changes,
            change_type="status_change",
            site_name=site_name,
            cloud_id=cloud_id,
            field="status",
            old=previous_status,
            new=current_status,
            severity=severity
        )


def _compare_endpoint_checks(changes, site_name, cloud_id, previous_site, current_site):
    previous_checks = previous_site.get("api_checks", {}) or {}
    current_checks = current_site.get("api_checks", {}) or {}

    endpoint_names = sorted(set(previous_checks.keys()) | set(current_checks.keys()))

    for endpoint_name in endpoint_names:
        previous_ok = previous_checks.get(endpoint_name)
        current_ok = current_checks.get(endpoint_name)

        if previous_ok != current_ok:
            severity = "warning"
            if current_ok is True:
                severity = "info"

            _append_change(
                changes=changes,
                change_type="endpoint_check_change",
                site_name=site_name,
                cloud_id=cloud_id,
                field=endpoint_name,
                old=previous_ok,
                new=current_ok,
                severity=severity
            )


def _compare_site(previous_site, current_site):
    changes = []

    site_name = current_site.get("name")
    cloud_id = current_site.get("cloud_id")

    _compare_status(previous_site, current_site, changes)

    _compare_numeric_metric(changes, previous_site, current_site, "project_count", severity="info")
    _compare_numeric_metric(changes, previous_site, current_site, "issue_count_total", severity="info")
    _compare_numeric_metric(changes, previous_site, current_site, "issue_count_unresolved", severity="warning")
    _compare_numeric_metric(changes, previous_site, current_site, "issue_count_updated_last_7d", severity="info")

    _compare_numeric_metric(changes, previous_site, current_site, "total_users", severity="warning")
    _compare_numeric_metric(changes, previous_site, current_site, "active_users", severity="warning")
    _compare_numeric_metric(changes, previous_site, current_site, "inactive_users", severity="warning")
    _compare_numeric_metric(changes, previous_site, current_site, "licensed_users_estimate", severity="warning")

    _compare_numeric_metric(changes, previous_site, current_site, "risk_score", severity="warning")

    _compare_list_field(
        changes,
        site_name,
        cloud_id,
        "permission_limited_checks",
        previous_site,
        current_site,
        severity="info"
    )

    _compare_list_field(
        changes,
        site_name,
        cloud_id,
        "blocking_failed_checks",
        previous_site,
        current_site,
        severity="warning"
    )

    _compare_list_field(
        changes,
        site_name,
        cloud_id,
        "status_reasons",
        previous_site,
        current_site,
        severity="info"
    )

    _compare_endpoint_checks(changes, site_name, cloud_id, previous_site, current_site)

    return changes


def _build_summary(snapshot):
    if not snapshot:
        return {
            "site_count": 0,
            "healthy_count": 0,
            "warning_count": 0,
            "critical_count": 0,
            "total_risk_score": 0,
            "average_risk_score": 0,
            "total_blocking_failures": 0,
            "total_permission_limited_checks": 0
        }

    return {
        "site_count": snapshot.get("site_count", 0),
        "healthy_count": snapshot.get("healthy_count", 0),
        "warning_count": snapshot.get("warning_count", 0),
        "critical_count": snapshot.get("critical_count", 0),
        "total_risk_score": snapshot.get("total_risk_score", 0),
        "average_risk_score": snapshot.get("average_risk_score", 0),
        "total_blocking_failures": snapshot.get("total_blocking_failures", 0),
        "total_permission_limited_checks": snapshot.get("total_permission_limited_checks", 0)
    }


def _compare_summary(previous_snapshot, current_snapshot):
    previous_summary = _build_summary(previous_snapshot)
    current_summary = _build_summary(current_snapshot)

    summary_changes = {}

    for key in current_summary.keys():
        previous_value = previous_summary.get(key, 0)
        current_value = current_summary.get(key, 0)

        if previous_value != current_value:
            summary_changes[key] = {
                "old": previous_value,
                "new": current_value
            }

    return {
        "previous": previous_summary,
        "current": current_summary,
        "changes": summary_changes
    }


def _count_severity(changes, severity_name):
    count = 0
    for change in changes:
        if (change.get("severity") or "info").lower() == severity_name:
            count += 1
    return count


def _growth_status_from_deltas(project_delta, total_users_delta, licensed_delta):
    values = []

    for value in [project_delta, total_users_delta, licensed_delta]:
        if isinstance(value, int):
            values.append(value)

    if not values:
        return "baseline"

    score = 0
    for value in values:
        if value > 0:
            score += 1
        elif value < 0:
            score -= 1

    if score > 0:
        return "growing"
    if score < 0:
        return "reducing"
    return "stable"


def apply_snapshot_deltas(previous_snapshot, current_collection):
    previous_sites = _build_site_lookup(previous_snapshot)
    current_sites = current_collection.get("sites", []) or []

    delta_summary = {
        "project_delta_total": 0,
        "total_users_delta_total": 0,
        "active_users_delta_total": 0,
        "inactive_users_delta_total": 0,
        "licensed_users_estimate_delta_total": 0
    }

    updated_sites = []

    for site in current_sites:
        cloud_id = site.get("cloud_id")
        previous_site = previous_sites.get(cloud_id)

        updated_site = dict(site)

        if not previous_site:
            updated_site["snapshot_baseline"] = True
            updated_site["project_count_delta"] = None
            updated_site["total_users_delta"] = None
            updated_site["active_users_delta"] = None
            updated_site["inactive_users_delta"] = None
            updated_site["licensed_users_estimate_delta"] = None
            updated_site["issue_count_total_delta"] = None
            updated_site["issue_count_unresolved_delta"] = None
            updated_site["growth_status"] = "baseline"

            updated_sites.append(updated_site)
            continue

        project_delta = _site_metric(site, "project_count") - _site_metric(previous_site, "project_count")
        total_users_delta = _site_metric(site, "total_users") - _site_metric(previous_site, "total_users")
        active_users_delta = _site_metric(site, "active_users") - _site_metric(previous_site, "active_users")
        inactive_users_delta = _site_metric(site, "inactive_users") - _site_metric(previous_site, "inactive_users")
        licensed_delta = _site_metric(site, "licensed_users_estimate") - _site_metric(previous_site, "licensed_users_estimate")
        issue_total_delta = _site_metric(site, "issue_count_total") - _site_metric(previous_site, "issue_count_total")
        unresolved_delta = _site_metric(site, "issue_count_unresolved") - _site_metric(previous_site, "issue_count_unresolved")

        updated_site["snapshot_baseline"] = False
        updated_site["project_count_delta"] = project_delta
        updated_site["total_users_delta"] = total_users_delta
        updated_site["active_users_delta"] = active_users_delta
        updated_site["inactive_users_delta"] = inactive_users_delta
        updated_site["licensed_users_estimate_delta"] = licensed_delta
        updated_site["issue_count_total_delta"] = issue_total_delta
        updated_site["issue_count_unresolved_delta"] = unresolved_delta
        updated_site["growth_status"] = _growth_status_from_deltas(
            project_delta=project_delta,
            total_users_delta=total_users_delta,
            licensed_delta=licensed_delta
        )

        delta_summary["project_delta_total"] += project_delta
        delta_summary["total_users_delta_total"] += total_users_delta
        delta_summary["active_users_delta_total"] += active_users_delta
        delta_summary["inactive_users_delta_total"] += inactive_users_delta
        delta_summary["licensed_users_estimate_delta_total"] += licensed_delta

        updated_sites.append(updated_site)

    updated_collection = dict(current_collection)
    updated_collection["sites"] = updated_sites
    updated_collection["delta_summary"] = delta_summary

    return updated_collection


def compare_snapshots(previous_snapshot, current_snapshot):
    if not previous_snapshot:
        return {
            "has_previous_snapshot": False,
            "summary": _compare_summary(None, current_snapshot),
            "change_count": 0,
            "info_change_count": 0,
            "warning_change_count": 0,
            "critical_change_count": 0,
            "changes": []
        }

    previous_sites = _build_site_lookup(previous_snapshot)
    current_sites = _build_site_lookup(current_snapshot)

    changes = []

    for cloud_id, current_site in current_sites.items():
        previous_site = previous_sites.get(cloud_id)

        if not previous_site:
            _append_change(
                changes=changes,
                change_type="new_site",
                site_name=current_site.get("name"),
                cloud_id=cloud_id,
                severity="info"
            )
            continue

        changes.extend(_compare_site(previous_site, current_site))

    for cloud_id, previous_site in previous_sites.items():
        if cloud_id not in current_sites:
            _append_change(
                changes=changes,
                change_type="removed_site",
                site_name=previous_site.get("name"),
                cloud_id=cloud_id,
                severity="warning"
            )

    summary = _compare_summary(previous_snapshot, current_snapshot)

    return {
        "has_previous_snapshot": True,
        "summary": summary,
        "change_count": len(changes),
        "info_change_count": _count_severity(changes, "info"),
        "warning_change_count": _count_severity(changes, "warning"),
        "critical_change_count": _count_severity(changes, "critical"),
        "changes": changes
    }