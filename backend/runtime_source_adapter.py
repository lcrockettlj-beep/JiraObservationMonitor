"""
backend/runtime_source_adapter.py
Runtime-only source adapter.

Rules:
- Prefer latest_run.json as the canonical source of truth.
- Fall back to latest_run_safe_partial.json only if latest_run.json does not exist.
- Fall back to pretty/report variants only if no better canonical file exists.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import glob
import json
import re

RUNTIME_CANDIDATE_GROUPS = [
    [
        "latest_run.json",
        "reports/latest_run.json",
    ],
    [
        "latest_run_safe_partial.json",
        "reports/latest_run_safe_partial.json",
    ],
    [
        "latest_run_pretty.json",
        "reports/latest_run_pretty.json",
    ],
    [
        "latest_run*.json",
        "reports/latest_run*.json",
    ],
]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return content if isinstance(content, dict) else None


def _candidate_paths(base_dir: Path) -> List[Path]:
    seen = set()
    ordered: List[Path] = []

    for group in RUNTIME_CANDIDATE_GROUPS:
        group_paths: List[Path] = []
        for pattern in group:
            for match in glob.glob(str(base_dir / pattern)):
                path = Path(match)
                key = str(path.resolve())
                if key in seen or not path.is_file():
                    continue
                seen.add(key)
                group_paths.append(path)

        if any("*" in pattern for pattern in group):
            group_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        ordered.extend(group_paths)

    return ordered


def _slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower())
    return value.strip("-")


def _derive_site_key(site: Dict[str, Any]) -> str:
    existing = str(site.get("site") or site.get("site_key") or "").strip()
    if existing:
        return existing

    url = str(site.get("url") or "").strip().lower()
    if url:
        host = url.replace("https://", "").replace("http://", "").split("/")[0]
        if host.endswith(".atlassian.net"):
            return host[:-len(".atlassian.net")]
        return host

    name = str(site.get("site_name") or site.get("name") or "").strip()
    if name:
        return _slugify(name)

    cloud_id = str(site.get("cloud_id") or "").strip()
    if cloud_id:
        return cloud_id

    return "site"


def _derive_site_name(site: Dict[str, Any], site_key: str) -> str:
    return (
        str(site.get("site_name") or "").strip()
        or str(site.get("name") or "").strip()
        or site_key
    )


def _payload_to_sites(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload.get("sites"), list):
        return [item for item in payload.get("sites", []) if isinstance(item, dict)]
    if isinstance(payload.get("site_summaries"), list):
        return [item for item in payload.get("site_summaries", []) if isinstance(item, dict)]

    site_map = payload.get("site_map")
    if isinstance(site_map, dict):
        rows: List[Dict[str, Any]] = []
        for site_key, value in site_map.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("site", site_key)
                row.setdefault("site_key", site_key)
                row.setdefault("name", value.get("site_name") or site_key)
                rows.append(row)
        return rows

    collector_sites = payload.get("collector_sites")
    if isinstance(collector_sites, list):
        return [item for item in collector_sites if isinstance(item, dict)]

    return []


def _normalise_project_rows(raw_rows: Any, site_key: str, site_name: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for project in _safe_list(raw_rows):
        if not isinstance(project, dict):
            continue
        row = dict(project)
        row.setdefault("site", site_key)
        row.setdefault("site_key", site_key)
        row.setdefault("site_name", site_name)
        row.setdefault("project_key", project.get("key", ""))
        row.setdefault("project_name", project.get("name", ""))
        row.setdefault("project_type", project.get("projectTypeKey") or project.get("project_type_key") or "")
        row.setdefault("simplified", project.get("simplified"))
        rows.append(row)
    return rows


def _normalise_site_record(site: Dict[str, Any]) -> Dict[str, Any]:
    site_key = _derive_site_key(site)
    site_name = _derive_site_name(site, site_key)
    user_summary = _safe_dict(site.get("user_summary"))
    licence_summary = _safe_dict(site.get("licence_summary"))
    project_rows = _normalise_project_rows(site.get("project_rows") or site.get("project_sample") or [], site_key, site_name)

    normalised = dict(site)
    normalised["site"] = site_key
    normalised["site_key"] = site_key
    normalised["site_name"] = site_name
    normalised["name"] = site_name
    normalised["url"] = site.get("url")
    normalised["cloud_id"] = site.get("cloud_id")

    normalised["project_rows"] = project_rows
    normalised["project_sample"] = project_rows
    normalised["sampled_project_rows"] = len(project_rows)
    normalised["project_sample_available"] = bool(project_rows)

    normalised["project_count"] = site.get("project_count")
    normalised["issue_count_total"] = site.get("issue_count_total")
    normalised["issue_count_unresolved"] = site.get("issue_count_unresolved")
    normalised["issue_count_updated_last_7d"] = site.get("issue_count_updated_last_7d")
    normalised["project_count_delta"] = site.get("project_count_delta", 0)

    normalised["total_users"] = user_summary.get("total_users")
    normalised["active_users"] = user_summary.get("active_users")
    normalised["inactive_users"] = user_summary.get("inactive_users")
    normalised["licensed_users"] = licence_summary.get("licensed_users_estimate")
    normalised["licensed_users_estimate"] = licence_summary.get("licensed_users_estimate")

    normalised["status"] = site.get("status") or "stable"
    normalised["reason"] = "; ".join([str(item) for item in _safe_list(site.get("status_reasons")) if str(item).strip()])
    normalised["status_reasons"] = _safe_list(site.get("status_reasons"))
    normalised["atlassian_area"] = "Jira operational monitoring"

    normalised["growth_status"] = site.get("growth_status") or "stable"
    normalised["total_users_delta"] = site.get("total_users_delta", 0)
    normalised["active_users_delta"] = site.get("active_users_delta", 0)
    normalised["inactive_users_delta"] = site.get("inactive_users_delta", 0)
    normalised["licensed_users_estimate_delta"] = site.get("licensed_users_estimate_delta", 0)

    normalised["risk_score"] = site.get("risk_score", 0)
    normalised["trend_signals"] = _safe_list(site.get("trend_signals"))
    normalised["attention_reasons"] = _safe_list(site.get("attention_reasons"))
    normalised["permission_limited_checks"] = _safe_list(site.get("permission_limited_checks"))

    return normalised


def _sum_if_known(items: List[Dict[str, Any]], key: str) -> Optional[int]:
    values = [item.get(key) for item in items if item.get(key) is not None]
    if not values:
        return None
    try:
        return sum(int(v) for v in values)
    except Exception:
        return None


def _build_estate(payload: Dict[str, Any], sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = _safe_dict(payload.get("summary"))
    risk_summary = _safe_dict(payload.get("risk_summary"))
    delta_summary = _safe_dict(payload.get("delta_summary"))
    existing_estate = _safe_dict(payload.get("estate"))

    estate = dict(existing_estate)
    estate.setdefault("total_sites", summary.get("site_count", len(sites)))
    estate.setdefault("total_projects", summary.get("project_count_total"))
    estate.setdefault("total_issues", summary.get("issue_count_total"))
    estate.setdefault("total_unresolved_issues", summary.get("issue_count_unresolved_total"))
    estate.setdefault("total_recent_issues", summary.get("issue_count_updated_last_7d_total"))

    estate.setdefault("critical_site_count", risk_summary.get("critical_site_count", 0))
    estate.setdefault("warning_site_count", risk_summary.get("warning_site_count", 0))
    estate.setdefault("stable_site_count", risk_summary.get("stable_site_count", 0))
    estate.setdefault("permission_limited_site_count", risk_summary.get("permission_limited_site_count", 0))

    estate.setdefault("project_delta_total", delta_summary.get("project_delta_total", 0))
    estate.setdefault("total_users_delta_total", delta_summary.get("total_users_delta_total", 0))
    estate.setdefault("active_users_delta_total", delta_summary.get("active_users_delta_total", 0))
    estate.setdefault("inactive_users_delta_total", delta_summary.get("inactive_users_delta_total", 0))
    estate.setdefault("licensed_users_estimate_delta_total", delta_summary.get("licensed_users_estimate_delta_total", 0))

    estate.setdefault("total_users", _sum_if_known(sites, "total_users"))
    estate.setdefault("total_active_users", _sum_if_known(sites, "active_users"))
    estate.setdefault("total_inactive_users", _sum_if_known(sites, "inactive_users"))
    estate.setdefault("licensed_users_estimate", _sum_if_known(sites, "licensed_users"))

    estate.setdefault("managed_disabled_accounts", existing_estate.get("managed_disabled_accounts"))
    estate.setdefault("no_tracked_jira_site_access", existing_estate.get("no_tracked_jira_site_access"))
    estate.setdefault("inactive_without_site_access", existing_estate.get("inactive_without_site_access"))
    estate.setdefault("bitbucket_only_no_tracked_jira", existing_estate.get("bitbucket_only_no_tracked_jira"))
    estate.setdefault("run_timestamp_local", payload.get("run_timestamp_local"))
    return estate


def _build_runtime_drilldowns(payload: Dict[str, Any], sites: List[Dict[str, Any]]) -> Dict[str, Any]:
    drilldowns = _safe_dict(payload.get("drilldowns"))

    site_rows = []
    for site in sites:
        site_rows.append({
            "site_name": site.get("site_name"),
            "site_key": site.get("site"),
            "status": site.get("status"),
            "project_count": site.get("project_count"),
            "issue_count_total": site.get("issue_count_total"),
            "issue_count_unresolved": site.get("issue_count_unresolved"),
            "issue_count_updated_last_7d": site.get("issue_count_updated_last_7d"),
            "total_users": site.get("total_users"),
            "active_users": site.get("active_users"),
            "inactive_users": site.get("inactive_users"),
            "reason": site.get("reason"),
        })

    if site_rows:
        drilldowns.setdefault(
            "site::summary",
            {
                "title": "Monitored Site Summary",
                "reason": "This summary reflects the latest runtime collector payload across the monitored Jira estate.",
                "atlassian_area": "Jira operational monitoring",
                "columns": [
                    "site_name",
                    "site_key",
                    "status",
                    "project_count",
                    "issue_count_total",
                    "issue_count_unresolved",
                    "issue_count_updated_last_7d",
                    "total_users",
                    "active_users",
                    "inactive_users",
                    "reason",
                ],
                "rows": site_rows,
            },
        )

    for site in sites:
        site_key = site.get("site")
        site_name = site.get("site_name")
        drilldowns.setdefault(
            f"site::{site_key}",
            {
                "title": f"Site Detail — {site_name}",
                "reason": "This detail view reflects the current collector payload for this monitored Jira site.",
                "atlassian_area": "Jira operational monitoring",
                "columns": [
                    "site_name",
                    "status",
                    "project_count",
                    "issue_count_total",
                    "issue_count_unresolved",
                    "issue_count_updated_last_7d",
                    "total_users",
                    "active_users",
                    "inactive_users",
                    "reason",
                ],
                "rows": [{
                    "site_name": site_name,
                    "status": site.get("status"),
                    "project_count": site.get("project_count"),
                    "issue_count_total": site.get("issue_count_total"),
                    "issue_count_unresolved": site.get("issue_count_unresolved"),
                    "issue_count_updated_last_7d": site.get("issue_count_updated_last_7d"),
                    "total_users": site.get("total_users"),
                    "active_users": site.get("active_users"),
                    "inactive_users": site.get("inactive_users"),
                    "reason": site.get("reason"),
                }],
            },
        )

    return drilldowns


def _normalise_payload(payload: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    data = dict(payload)
    raw_sites = _payload_to_sites(payload)
    sites = [_normalise_site_record(site) for site in raw_sites]

    data["sites"] = sites
    data["estate"] = _build_estate(payload, sites)
    data["drilldowns"] = _build_runtime_drilldowns(payload, sites)
    data["org_product_breakdown"] = _safe_list(payload.get("org_product_breakdown"))
    data["users_export_breakdown"] = _safe_list(payload.get("users_export_breakdown"))

    source_label = f"Runtime payload: {source_file}"
    data.setdefault("users_source_file", source_label)
    data.setdefault("managed_source_file", source_label)
    data.setdefault("users_row_count", len(_safe_list(payload.get("users"))))
    data.setdefault("managed_row_count", len(_safe_list(payload.get("managed_accounts"))))
    data["source_mode"] = "runtime"
    data["source_file"] = source_file
    return data


def load_preferred_source_payload(base_dir: Path) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    for path in _candidate_paths(base_dir):
        payload = _read_json(path)
        if not payload:
            continue
        normalised = _normalise_payload(payload, path.name)
        has_sites = bool(normalised.get("sites"))
        has_estate = bool(normalised.get("estate"))
        has_drilldowns = bool(normalised.get("drilldowns"))
        if not (has_sites or has_estate or has_drilldowns):
            continue
        return normalised, {
            "mode": "runtime",
            "file": path.name,
            "path": str(path),
        }
    return None, {
        "mode": "runtime",
        "file": None,
        "path": None,
    }
