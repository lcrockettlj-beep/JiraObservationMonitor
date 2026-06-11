from datetime import datetime, timezone

from jira_client import get_accessible_resources, safe_jira_get


def _extract_project_count(project_payload):
    if not project_payload:
        return 0

    if isinstance(project_payload, dict):
        if isinstance(project_payload.get("total"), int):
            return project_payload["total"]

        values = project_payload.get("values")
        if isinstance(values, list):
            return len(values)

    return 0


def _extract_project_sample(project_payload, limit=10):
    if not project_payload or not isinstance(project_payload, dict):
        return []

    values = project_payload.get("values", [])
    if not isinstance(values, list):
        return []

    sample = []

    for project in values[:limit]:
        if not isinstance(project, dict):
            continue

        sample.append({
            "id": project.get("id"),
            "key": project.get("key"),
            "name": project.get("name"),
            "project_type_key": project.get("projectTypeKey"),
            "simplified": project.get("simplified"),
            "style": project.get("style"),
            "is_private": project.get("isPrivate"),
        })

    return sample


def _extract_application_role_count(role_payload):
    if isinstance(role_payload, list):
        return len(role_payload)

    return 0


def _extract_application_role_sample(role_payload):
    if not isinstance(role_payload, list):
        return []

    sample = []

    for role in role_payload[:10]:
        if not isinstance(role, dict):
            continue

        sample.append({
            "key": role.get("key"),
            "name": role.get("name"),
            "default_groups_count": len(role.get("defaultGroups", []) or []),
            "selected_by_default": role.get("selectedByDefault"),
            "defined": role.get("defined")
        })

    return sample


def _extract_issue_total(search_payload):
    if not search_payload or not isinstance(search_payload, dict):
        return 0

    total = search_payload.get("total")
    if isinstance(total, int):
        return total

    return 0


def _extract_server_info_summary(server_info_payload):
    if not isinstance(server_info_payload, dict):
        return None

    return {
        "base_url": server_info_payload.get("baseUrl"),
        "display_url": server_info_payload.get("displayUrl"),
        "deployment_type": server_info_payload.get("deploymentType"),
        "version": server_info_payload.get("version"),
        "build_number": server_info_payload.get("buildNumber"),
        "build_date": server_info_payload.get("buildDate"),
        "server_time": server_info_payload.get("serverTime"),
        "server_title": server_info_payload.get("serverTitle"),
        "default_locale": (server_info_payload.get("defaultLocale") or {}).get("locale"),
        "server_time_zone": server_info_payload.get("serverTimeZone")
    }


def _extract_myself_summary(myself_payload):
    if not isinstance(myself_payload, dict):
        return None

    groups_info = myself_payload.get("groups") or {}
    application_roles_info = myself_payload.get("applicationRoles") or {}

    return {
        "account_id": myself_payload.get("accountId"),
        "account_type": myself_payload.get("accountType"),
        "display_name": myself_payload.get("displayName"),
        "active": myself_payload.get("active"),
        "time_zone": myself_payload.get("timeZone"),
        "locale": myself_payload.get("locale"),
        "group_count_visible": groups_info.get("size", 0),
        "application_role_count_visible": application_roles_info.get("size", 0)
    }


def _build_api_checks(result_map):
    checks = {}

    for key, value in result_map.items():
        checks[key] = bool(value.get("ok"))

    return checks


def _build_api_errors(result_map):
    errors = {}

    for key, value in result_map.items():
        errors[key] = value.get("error")

    return errors


def _build_endpoint_summary(api_checks, api_errors):
    total_checks = len(api_checks)
    successful_checks = 0
    failed_checks = 0
    permission_limited_checks = []

    for check_name, ok in api_checks.items():
        if ok:
            successful_checks += 1
            continue

        failed_checks += 1

        error_text = (api_errors.get(check_name) or "").lower()
        if "403" in error_text or "forbidden" in error_text:
            permission_limited_checks.append(check_name)

    return {
        "total_checks": total_checks,
        "successful_checks": successful_checks,
        "failed_checks": failed_checks,
        "permission_limited_checks": permission_limited_checks
    }


def _collect_site_metrics(access_token, cloud_id):
    """
    Collects all endpoint responses for a single Jira site.
    Every call is wrapped with safe_jira_get so one failed endpoint
    does not break the entire site collection.
    """
    server_info = safe_jira_get(access_token, cloud_id, "serverInfo")

    myself = safe_jira_get(
        access_token,
        cloud_id,
        "myself",
        params={"expand": "groups,applicationRoles"}
    )

    projects = safe_jira_get(
        access_token,
        cloud_id,
        "project/search",
        params={"maxResults": 100}
    )

    application_roles = safe_jira_get(
        access_token,
        cloud_id,
        "applicationrole"
    )

    all_issues = safe_jira_get(
        access_token,
        cloud_id,
        "search",
        params={
            "jql": "order by created desc",
            "maxResults": 0
        }
    )

    unresolved_issues = safe_jira_get(
        access_token,
        cloud_id,
        "search",
        params={
            "jql": "resolution = Unresolved",
            "maxResults": 0
        }
    )

    updated_last_7d = safe_jira_get(
        access_token,
        cloud_id,
        "search",
        params={
            "jql": "updated >= -7d",
            "maxResults": 0
        }
    )

    return {
        "server_info": server_info,
        "myself": myself,
        "projects": projects,
        "application_roles": application_roles,
        "all_issues": all_issues,
        "unresolved_issues": unresolved_issues,
        "updated_last_7d": updated_last_7d
    }


def collect_site_data(access_token, resource):
    cloud_id = resource.get("id")
    site_name = resource.get("name") or resource.get("url") or cloud_id
    site_url = resource.get("url")
    site_scopes = resource.get("scopes", [])
    avatar_url = resource.get("avatarUrl")

    result_map = _collect_site_metrics(access_token, cloud_id)

    api_checks = _build_api_checks(result_map)
    api_errors = _build_api_errors(result_map)
    endpoint_summary = _build_endpoint_summary(api_checks, api_errors)

    server_info_data = result_map["server_info"]["data"] if result_map["server_info"]["ok"] else None
    myself_data = result_map["myself"]["data"] if result_map["myself"]["ok"] else None
    projects_data = result_map["projects"]["data"] if result_map["projects"]["ok"] else None
    application_roles_data = (
        result_map["application_roles"]["data"]
        if result_map["application_roles"]["ok"] else None
    )
    all_issues_data = result_map["all_issues"]["data"] if result_map["all_issues"]["ok"] else None
    unresolved_issues_data = (
        result_map["unresolved_issues"]["data"]
        if result_map["unresolved_issues"]["ok"] else None
    )
    updated_last_7d_data = (
        result_map["updated_last_7d"]["data"]
        if result_map["updated_last_7d"]["ok"] else None
    )

    project_count = _extract_project_count(projects_data)
    project_sample = _extract_project_sample(projects_data, limit=10)

    application_role_count = _extract_application_role_count(application_roles_data)
    application_role_sample = _extract_application_role_sample(application_roles_data)

    total_issue_count = _extract_issue_total(all_issues_data)
    unresolved_issue_count = _extract_issue_total(unresolved_issues_data)
    updated_last_7d_count = _extract_issue_total(updated_last_7d_data)

    site_record = {
        "name": site_name,
        "url": site_url,
        "cloud_id": cloud_id,
        "avatar_url": avatar_url,
        "scopes": site_scopes,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),

        # Core metrics
        "project_count": project_count,
        "application_role_count": application_role_count,
        "issue_count_total": total_issue_count,
        "issue_count_unresolved": unresolved_issue_count,
        "issue_count_updated_last_7d": updated_last_7d_count,

        # Samples / summaries
        "project_sample": project_sample,
        "application_role_sample": application_role_sample,
        "server_info": _extract_server_info_summary(server_info_data),
        "myself": _extract_myself_summary(myself_data),

        # API health
        "api_checks": api_checks,
        "api_errors": api_errors,
        "endpoint_summary": endpoint_summary
    }

    return site_record


def collect_all_sites(access_token):
    resources = get_accessible_resources(access_token)

    sites = []

    for resource in resources:
        site_record = collect_site_data(access_token, resource)
        sites.append(site_record)

    return {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "site_count": len(sites),
        "sites": sites
    }