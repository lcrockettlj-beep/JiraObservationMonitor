import json
import os


def _safe_list(value):
    return value if isinstance(value, list) else []


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _normalise_site_key_from_url(url):
    if not url:
        return None
    text = str(url).strip().lower()
    if text.startswith("https://"):
        text = text[len("https://"):]
    elif text.startswith("http://"):
        text = text[len("http://"):]
    host = text.split("/")[0]
    if host.endswith(".atlassian.net"):
        return host[:-len(".atlassian.net")]
    return host or None


def _normalise_site_key_from_name(name):
    if not name:
        return None
    text = str(name).strip().lower().replace(" ", "-")
    return text or None


def _site_key_for_record(site):
    if not isinstance(site, dict):
        return None
    return (
        site.get("site")
        or site.get("site_key")
        or _normalise_site_key_from_url(site.get("url"))
        or _normalise_site_key_from_name(site.get("site_name") or site.get("name"))
        or site.get("cloud_id")
    )


def _site_name_for_record(site, site_key):
    return site.get("site_name") or site.get("name") or site_key


def _yes_no(value):
    return "Yes" if bool(value) else "No"


def _load_latest_run(file_name="latest_run.json"):
    if not os.path.exists(file_name):
        return {}
    try:
        with open(file_name, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalise_project_rows(site, site_key, site_name):
    project_rows = site.get("project_rows") or site.get("project_sample") or []
    rows = []
    for project in _safe_list(project_rows):
        if not isinstance(project, dict):
            continue
        row = {
            "site_name": site_name,
            "site_key": site_key,
            "project_id": project.get("id", ""),
            "project_key": project.get("project_key") or project.get("key", ""),
            "project_name": project.get("project_name") or project.get("name", ""),
            "project_type": project.get("project_type") or project.get("projectTypeKey") or project.get("project_type_key", ""),
            "style": project.get("style", ""),
            "simplified": _yes_no(project.get("simplified")),
            "is_private": _yes_no(project.get("is_private") if "is_private" in project else project.get("isPrivate")),
        }
        rows.append(row)
    return rows


def load_project_counts_from_latest_run(file_name="latest_run.json"):
    data = _load_latest_run(file_name)
    sites = _safe_list(data.get("sites"))
    result = {}
    for site in sites:
        if not isinstance(site, dict):
            continue
        site_key = _site_key_for_record(site)
        if not site_key:
            continue
        result[site_key] = {
            "project_count": site.get("project_count"),
            "issue_count_total": site.get("issue_count_total"),
            "issue_count_unresolved": site.get("issue_count_unresolved"),
            "issue_count_updated_last_7d": site.get("issue_count_updated_last_7d"),
            "project_count_delta": site.get("project_count_delta", 0),
        }
    return result


def load_project_intelligence_from_latest_run(file_name="latest_run.json"):
    data = _load_latest_run(file_name)
    if not data:
        return {
            "has_current_run": False,
            "site_map": {},
            "all_projects": [],
            "summary_rows": [],
        }

    site_map = {}
    all_projects = []
    summary_rows = []

    for site in _safe_list(data.get("sites")):
        if not isinstance(site, dict):
            continue
        site_key = _site_key_for_record(site)
        if not site_key:
            continue
        site_name = _site_name_for_record(site, site_key)
        project_rows = _normalise_project_rows(site, site_key, site_name)

        site_record = {
            "site": site_key,
            "site_name": site_name,
            "cloud_id": site.get("cloud_id", ""),
            "project_count": site.get("project_count", 0),
            "project_count_delta": site.get("project_count_delta", 0),
            "issue_count_total": site.get("issue_count_total", 0),
            "issue_count_unresolved": site.get("issue_count_unresolved", 0),
            "issue_count_updated_last_7d": site.get("issue_count_updated_last_7d", 0),
            "sampled_project_rows": len(project_rows),
            "project_rows": project_rows,
        }
        site_map[site_key] = site_record
        all_projects.extend(project_rows)
        summary_rows.append({
            "site_name": site_name,
            "project_count": site.get("project_count", 0),
            "project_count_delta": site.get("project_count_delta", 0),
            "issue_count_total": site.get("issue_count_total", 0),
            "issue_count_unresolved": site.get("issue_count_unresolved", 0),
            "issue_count_updated_last_7d": site.get("issue_count_updated_last_7d", 0),
            "sampled_project_rows": len(project_rows),
        })

    all_projects.sort(key=lambda row: (str(row.get("site_name", "")).lower(), str(row.get("project_key", "")).lower()))
    summary_rows.sort(key=lambda row: str(row.get("site_name", "")).lower())

    return {
        "has_current_run": True,
        "site_map": site_map,
        "all_projects": all_projects,
        "summary_rows": summary_rows,
    }


def build_project_drilldowns_from_latest_run(file_name="latest_run.json"):
    intelligence = load_project_intelligence_from_latest_run(file_name)
    site_map = intelligence.get("site_map", {})
    all_projects = intelligence.get("all_projects", [])
    summary_rows = intelligence.get("summary_rows", [])

    drilldowns = {
        "project::summary": {
            "title": "Project Intelligence Summary",
            "reason": "This summary reflects the current collector project intelligence available from the latest runtime payload.",
            "atlassian_area": "Jira operational monitoring / project intelligence",
            "columns": [
                "site_name",
                "project_count",
                "project_count_delta",
                "issue_count_total",
                "issue_count_unresolved",
                "issue_count_updated_last_7d",
                "sampled_project_rows",
            ],
            "rows": summary_rows,
        },
        "project::all_samples": {
            "title": "Project Sample Inventory",
            "reason": "These are the real project rows returned by the latest collector snapshot across the monitored Jira sites.",
            "atlassian_area": "Jira operational monitoring / project intelligence",
            "columns": [
                "site_name",
                "project_key",
                "project_name",
                "project_type",
                "style",
                "simplified",
                "is_private",
            ],
            "rows": all_projects,
        },
    }

    for site_key, site_record in site_map.items():
        drilldowns[f"project::site::{site_key}"] = {
            "title": f"Project Sample — {site_record.get('site_name', site_key)}",
            "reason": "These rows reflect the real project sample returned by the latest collector snapshot for this monitored site.",
            "atlassian_area": "Jira operational monitoring / project intelligence",
            "columns": [
                "project_key",
                "project_name",
                "project_type",
                "style",
                "simplified",
                "is_private",
            ],
            "rows": site_record.get("project_rows", []),
        }

    return drilldowns
