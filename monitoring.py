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


def _compare_numeric_field(changes, site_name, cloud_id, field_name, previous_site, current_site, severity="info"):
    previous_value = previous_site.get(field_name, 0)
    current_value = current_site.get(field_name, 0)

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


def _compare_endpoint_checks(changes, site_name, cloud_id, previous_site, current_site):
    previous_checks = previous_site.get("api_checks", {}) or {}
    current_checks = current_site.get("api_checks", {}) or {}

    endpoint_names = sorted(set(previous_checks.keys()) | set(current_checks.keys()))

    for endpoint_name in endpoint_names:
        previous_ok = previous_checks.get(endpoint_name)
        current_ok = current_checks.get(endpoint_name)

        if previous_ok != current_ok:
            severity = "warning"
            if current_ok is False:
                severity = "warning"
            elif current_ok is True:
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

    _compare_numeric_field(changes, site_name, cloud_id, "project_count", previous_site, current_site, severity="info")
    _compare_numeric_field(changes, site_name, cloud_id, "application_role_count", previous_site, current_site, severity="info")
    _compare_numeric_field(changes, site_name, cloud_id, "issue_count_total", previous_site, current_site, severity="info")
    _compare_numeric_field(changes, site_name, cloud_id, "issue_count_unresolved", previous_site, current_site, severity="warning")
    _compare_numeric_field(changes, site_name, cloud_id, "issue_count_updated_last_7d", previous_site, current_site, severity="info")
    _compare_numeric_field(changes, site_name, cloud_id, "failed_api_checks", previous_site, current_site, severity="warning")

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
        "permission_limited_checks",
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
            "critical_count": 0
        }

    return {
        "site_count": snapshot.get("site_count", 0),
        "healthy_count": snapshot.get("healthy_count", 0),
        "warning_count": snapshot.get("warning_count", 0),
        "critical_count": snapshot.get("critical_count", 0)
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


def compare_snapshots(previous_snapshot, current_snapshot):
    if not previous_snapshot:
        return {
            "has_previous_snapshot": False,
            "summary": _compare_summary(None, current_snapshot),
            "change_count": 0,
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

        site_changes = _compare_site(previous_site, current_site)
        changes.extend(site_changes)

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
        "changes": changes
    }