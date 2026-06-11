import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from jira_client import (
    get_accessible_resources,
    safe_jira_get,
    safe_jira_search_count
)


MAX_SITE_WORKERS = int(os.getenv("JOM_MAX_SITE_WORKERS", "3"))
ENDPOINT_WORKERS = int(os.getenv("JOM_ENDPOINT_WORKERS", "3"))

IGNORED_SITE_NAMES = {
    name.strip().lower()
    for name in os.getenv("JOM_IGNORED_SITE_NAMES", "").split(",")
    if name.strip()
}

CORE_ENDPOINT_KEYS = {
    "server_info",
    "myself",
    "projects"
}

ENRICHMENT_ENDPOINT_KEYS = {
    "application_roles",
    "all_issues",
    "unresolved_issues",
    "updated_last_7d"
}


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_number(value, default=0):
    if isinstance(value, (int, float)):
        return value
    return default


def _extract_project_count(project_payload):
    if not project_payload:
        return 0

    if isinstance(project_payload, dict):
        total = project_payload.get("total")
        if isinstance(total, int):
            return total

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
            "is_private": project.get("isPrivate")
        })

    return sample


def _extract_application_role_count(role_payload):
    if isinstance(role_payload, list):
        return len(role_payload)
    return 0


def _extract_application_role_sample(role_payload, limit=10):
    if not isinstance(role_payload, list):
        return []

    sample = []

    for role in role_payload[:limit]:
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
    return {key: bool(value.get("ok")) for key, value in result_map.items()}


def _build_api_errors(result_map):
    return {key: value.get("error") for key, value in result_map.items()}


def _build_api_status_codes(result_map):
    return {key: value.get("status_code") for key, value in result_map.items()}


def _build_api_urls(result_map):
    return {key: value.get("url") for key, value in result_map.items()}


def _build_api_error_categories(result_map):
    return {key: value.get("error_category") for key, value in result_map.items()}


def _build_api_attempt_counts(result_map):
    return {key: value.get("attempt_count", 1) for key, value in result_map.items()}


def _build_search_debug(result_map):
    search_debug = {}

    for key, value in result_map.items():
        if key not in {"all_issues", "unresolved_issues", "updated_last_7d"}:
            continue

        search_debug[key] = {
            "used_fallback": value.get("used_fallback", False),
            "selected_jql": value.get("selected_jql"),
            "search_attempts": value.get("search_attempts", [])
        }

    return search_debug


def _build_endpoint_results(result_map):
    endpoint_results = {}

    for endpoint_key, result in result_map.items():
        endpoint_results[endpoint_key] = {
            "ok": result.get("ok"),
            "status_code": result.get("status_code"),
            "url": result.get("url"),
            "error": result.get("error"),
            "endpoint": result.get("endpoint"),
            "attempt_count": result.get("attempt_count", 1),
            "retryable": result.get("retryable", False),
            "error_category": result.get("error_category"),
            "method": result.get("method"),
            "used_fallback": result.get("used_fallback", False),
            "selected_jql": result.get("selected_jql")
        }

    return endpoint_results


def _endpoint_type(endpoint_key):
    if endpoint_key in CORE_ENDPOINT_KEYS:
        return "core"
    return "enrichment"


def _is_permission_limited(status_code, error_text, error_category):
    error_text = (error_text or "").lower()

    if error_category == "permission_limited":
        return True

    if status_code == 403:
        return True

    if "403" in error_text or "forbidden" in error_text:
        return True

    return False


def _build_endpoint_health_summary(api_checks, api_errors, api_status_codes, api_error_categories, api_urls):
    total_checks = len(api_checks)
    successful_checks = 0
    failed_checks = 0

    permission_limited_checks = []
    core_blocking_failed_checks = []
    enrichment_failed_checks = []

    failed_check_details = []
    permission_issue_urls = []
    error_category_counter = Counter()

    for check_name, ok in api_checks.items():
        if ok:
            successful_checks += 1
            continue

        failed_checks += 1

        error_text = api_errors.get(check_name)
        status_code = api_status_codes.get(check_name)
        error_category = api_error_categories.get(check_name)
        endpoint_type = _endpoint_type(check_name)
        related_url = api_urls.get(check_name)

        permission_limited = _is_permission_limited(status_code, error_text, error_category)

        if error_category:
            error_category_counter[error_category] += 1

        if permission_limited:
            permission_limited_checks.append(check_name)
            permission_issue_urls.append({
                "endpoint_key": check_name,
                "url": related_url,
                "status_code": status_code,
                "error_category": error_category
            })
        elif endpoint_type == "core":
            core_blocking_failed_checks.append(check_name)
        else:
            enrichment_failed_checks.append(check_name)

        failed_check_details.append({
            "endpoint_key": check_name,
            "endpoint_type": endpoint_type,
            "status_code": status_code,
            "error": error_text,
            "error_category": error_category,
            "permission_limited": permission_limited,
            "url": related_url
        })

    return {
        "total_checks": total_checks,
        "successful_checks": successful_checks,
        "failed_checks": failed_checks,
        "core_blocking_failed_checks": core_blocking_failed_checks,
        "enrichment_failed_checks": enrichment_failed_checks,
        "permission_limited_checks": permission_limited_checks,
        "permission_issue_urls": permission_issue_urls,
        "failed_check_details": failed_check_details,
        "error_category_counts": dict(error_category_counter)
    }


def _fetch_endpoint(access_token, cloud_id, endpoint_key, endpoint, params=None):
    result = safe_jira_get(
        access_token=access_token,
        cloud_id=cloud_id,
        endpoint=endpoint,
        params=params
    )
    return endpoint_key, result


def _fetch_search_count(access_token, cloud_id, endpoint_key, jql_variants):
    result = safe_jira_search_count(
        access_token=access_token,
        cloud_id=cloud_id,
        jql_variants=jql_variants,
        fields=["key"]
    )
    return endpoint_key, result


def _collect_site_metrics(access_token, cloud_id):
    result_map = {}

    with ThreadPoolExecutor(max_workers=ENDPOINT_WORKERS) as executor:
        futures = []

        futures.append(executor.submit(
            _fetch_endpoint,
            access_token,
            cloud_id,
            "server_info",
            "serverInfo",
            None
        ))

        futures.append(executor.submit(
            _fetch_endpoint,
            access_token,
            cloud_id,
            "myself",
            "myself",
            {"expand": "groups,applicationRoles"}
        ))

        futures.append(executor.submit(
            _fetch_endpoint,
            access_token,
            cloud_id,
            "projects",
            "project/search",
            {"maxResults": 100}
        ))

        futures.append(executor.submit(
            _fetch_endpoint,
            access_token,
            cloud_id,
            "application_roles",
            "applicationrole",
            None
        ))

        futures.append(executor.submit(
            _fetch_search_count,
            access_token,
            cloud_id,
            "all_issues",
            [
                "order by created desc",
                "project is not EMPTY"
            ]
        ))

        futures.append(executor.submit(
            _fetch_search_count,
            access_token,
            cloud_id,
            "unresolved_issues",
            [
                "resolution is EMPTY",
                "resolution = Unresolved"
            ]
        ))

        futures.append(executor.submit(
            _fetch_search_count,
            access_token,
            cloud_id,
            "updated_last_7d",
            [
                "updated >= -7d",
                "updated >= startOfDay(-7d)"
            ]
        ))

        for future in as_completed(futures):
            endpoint_key, result = future.result()
            result_map[endpoint_key] = result

    return result_map


def collect_site_data(access_token, resource):
    site_start = time.perf_counter()

    cloud_id = resource.get("id")
    site_name = resource.get("name") or resource.get("url") or cloud_id
    site_url = resource.get("url")
    site_scopes = resource.get("scopes", [])
    avatar_url = resource.get("avatarUrl")

    result_map = _collect_site_metrics(access_token, cloud_id)

    api_checks = _build_api_checks(result_map)
    api_errors = _build_api_errors(result_map)
    api_status_codes = _build_api_status_codes(result_map)
    api_urls = _build_api_urls(result_map)
    api_error_categories = _build_api_error_categories(result_map)
    api_attempt_counts = _build_api_attempt_counts(result_map)

    endpoint_health_summary = _build_endpoint_health_summary(
        api_checks=api_checks,
        api_errors=api_errors,
        api_status_codes=api_status_codes,
        api_error_categories=api_error_categories,
        api_urls=api_urls
    )

    endpoint_results = _build_endpoint_results(result_map)
    search_debug = _build_search_debug(result_map)

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
    application_role_sample = _extract_application_role_sample(application_roles_data, limit=10)

    total_issue_count = _extract_issue_total(all_issues_data)
    unresolved_issue_count = _extract_issue_total(unresolved_issues_data)
    updated_last_7d_count = _extract_issue_total(updated_last_7d_data)

    site_elapsed_seconds = round(time.perf_counter() - site_start, 4)

    return {
        "name": site_name,
        "url": site_url,
        "cloud_id": cloud_id,
        "avatar_url": avatar_url,
        "scopes": site_scopes,

        "collected_at_utc": _utc_now_iso(),
        "collection_duration_seconds": site_elapsed_seconds,

        "project_count": project_count,
        "application_role_count": application_role_count,
        "issue_count_total": total_issue_count,
        "issue_count_unresolved": unresolved_issue_count,
        "issue_count_updated_last_7d": updated_last_7d_count,

        "project_sample": project_sample,
        "application_role_sample": application_role_sample,
        "server_info": _extract_server_info_summary(server_info_data),
        "myself": _extract_myself_summary(myself_data),

        "api_checks": api_checks,
        "api_errors": api_errors,
        "api_status_codes": api_status_codes,
        "api_urls": api_urls,
        "api_error_categories": api_error_categories,
        "api_attempt_counts": api_attempt_counts,
        "endpoint_summary": endpoint_health_summary,
        "endpoint_results": endpoint_results,
        "search_debug": search_debug
    }


def _collect_site_wrapper(index, access_token, resource):
    return index, collect_site_data(access_token, resource)


def collect_all_sites(access_token):
    run_start = time.perf_counter()
    collected_at_utc = _utc_now_iso()

    resources = get_accessible_resources(access_token)

    filtered_resources = []
    excluded_sites = []

    for resource in resources:
        site_name = (resource.get("name") or "").strip()
        if site_name.lower() in IGNORED_SITE_NAMES:
            excluded_sites.append({
                "name": site_name,
                "url": resource.get("url"),
                "cloud_id": resource.get("id")
            })
            continue
        filtered_resources.append(resource)

    site_count = len(filtered_resources)

    if site_count == 0:
        return {
            "collected_at_utc": collected_at_utc,
            "collection_duration_seconds": 0,
            "site_count": 0,
            "excluded_sites": excluded_sites,
            "endpoint_totals": {
                "successful_checks": 0,
                "failed_checks": 0,
                "permission_limited_checks": 0,
                "core_blocking_failed_checks": 0,
                "enrichment_failed_checks": 0
            },
            "error_category_totals": {},
            "collector_settings": {
                "max_site_workers": MAX_SITE_WORKERS,
                "endpoint_workers": ENDPOINT_WORKERS,
                "site_workers_used": 0
            },
            "sites": []
        }

    site_workers_used = min(MAX_SITE_WORKERS, site_count)
    ordered_results = []

    with ThreadPoolExecutor(max_workers=site_workers_used) as executor:
        futures = {
            executor.submit(_collect_site_wrapper, index, access_token, resource): index
            for index, resource in enumerate(filtered_resources)
        }

        for future in as_completed(futures):
            index, site_record = future.result()
            ordered_results.append((index, site_record))

    ordered_results.sort(key=lambda item: item[0])
    sites = [site_record for _, site_record in ordered_results]

    total_duration_seconds = round(time.perf_counter() - run_start, 4)

    healthy_endpoint_checks = 0
    failed_endpoint_checks = 0
    permission_limited_endpoint_checks = 0
    core_blocking_failed_endpoint_checks = 0
    enrichment_failed_endpoint_checks = 0
    error_category_counter = Counter()

    for site in sites:
        endpoint_summary = site.get("endpoint_summary", {}) or {}

        healthy_endpoint_checks += _safe_number(endpoint_summary.get("successful_checks", 0), 0)
        failed_endpoint_checks += _safe_number(endpoint_summary.get("failed_checks", 0), 0)
        permission_limited_endpoint_checks += len(endpoint_summary.get("permission_limited_checks", []) or [])
        core_blocking_failed_endpoint_checks += len(endpoint_summary.get("core_blocking_failed_checks", []) or [])
        enrichment_failed_endpoint_checks += len(endpoint_summary.get("enrichment_failed_checks", []) or [])

        for category_name, count in (endpoint_summary.get("error_category_counts", {}) or {}).items():
            error_category_counter[category_name] += count

    return {
        "collected_at_utc": collected_at_utc,
        "collection_duration_seconds": total_duration_seconds,
        "site_count": len(sites),
        "excluded_sites": excluded_sites,
        "endpoint_totals": {
            "successful_checks": healthy_endpoint_checks,
            "failed_checks": failed_endpoint_checks,
            "permission_limited_checks": permission_limited_endpoint_checks,
            "core_blocking_failed_checks": core_blocking_failed_endpoint_checks,
            "enrichment_failed_checks": enrichment_failed_endpoint_checks
        },
        "error_category_totals": dict(error_category_counter),
        "collector_settings": {
            "max_site_workers": MAX_SITE_WORKERS,
            "endpoint_workers": ENDPOINT_WORKERS,
            "site_workers_used": site_workers_used
        },
        "sites": sites
    }