import json
import os


def _normalise_site_key_from_url(url):
    if not url:
        return None
    text = str(url).strip().lower()
    mappings = {
        "gli-it-project.atlassian.net": "gli-it-project",
        "gli-delivery-tm.atlassian.net": "gli-delivery-tm",
        "gli-global-technology.atlassian.net": "gli-global-technology",
    }
    for needle, site_key in mappings.items():
        if needle in text:
            return site_key
    return None


def _normalise_site_key_from_name(name):
    if not name:
        return None
    text = str(name).strip().lower()
    mappings = {
        "gli-it-project": "gli-it-project",
        "gli-delivery-tm": "gli-delivery-tm",
        "gli-global-technology": "gli-global-technology",
        "gli it project": "gli-it-project",
        "gli delivery tm": "gli-delivery-tm",
        "gli global technology": "gli-global-technology",
    }
    return mappings.get(text)


def _site_key_for_record(site):
    site_key = _normalise_site_key_from_url(site.get("url"))
    if site_key:
        return site_key
    return _normalise_site_key_from_name(site.get("name"))


def _yes_no(value):
    return "Yes" if bool(value) else "No"


def load_project_counts_from_latest_run(file_name="latest_run.json"):
    if not os.path.exists(file_name):
        return {}

    try:
        with open(file_name, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}

    sites = data.get("sites", []) or []
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
            "project_count_delta": site.get("project_count_delta"),
        }

    return result


def load_project_intelligence_from_latest_run(file_name="latest_run.json"):
    if not os.path.exists(file_name):
        return {
            "has_current_run": False,
            "site_map": {},
            "all_projects": [],
            "summary_rows": [],
        }

    try:
        with open(file_name, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {
            "has_current_run": False,
            "site_map": {},
            "all_projects": [],
            "summary_rows": [],
        }

    site_map = {}
    all_projects = []
    summary_rows = []

    for site in data.get("sites", []) or []:
        if not isinstance(site, dict):
            continue

        site_key = _site_key_for_record(site)
        if not site_key:
            continue

        site_name = site.get("name", "")
        project_sample = site.get("project_sample", []) or []

        project_rows = []
        for project in project_sample:
            if not isinstance(project, dict):
                continue

            row = {
                "site_name": site_name,
                "site_key": site_key,
                "project_id": project.get("id", ""),
                "project_key": project.get("key", ""),
                "project_name": project.get("name", ""),
                "project_type": project.get("project_type_key", ""),
                "style": project.get("style", ""),
                "simplified": _yes_no(project.get("simplified")),
                "is_private": _yes_no(project.get("is_private")),
            }
            project_rows.append(row)
            all_projects.append(row)

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
            "reason": "This summary reflects the current collector project intelligence available from the latest run. Project-level last activity is not yet available in the current collector payload, so only real count/sample-based fields are shown.",
            "atlassian_area": "Jira operational monitoring / project intelligence",
            "columns": ["site_name", "project_count", "project_count_delta", "issue_count_total", "issue_count_unresolved", "issue_count_updated_last_7d", "sampled_project_rows"],
            "rows": summary_rows,
        },
        "project::all_samples": {
            "title": "Project Sample Inventory",
            "reason": "These are the real project sample rows returned by the latest collector snapshot across the monitored Jira sites. This is a sample view only, not a full project inventory.",
            "atlassian_area": "Jira operational monitoring / project intelligence",
            "columns": ["site_name", "project_key", "project_name", "project_type", "style", "simplified", "is_private"],
            "rows": all_projects,
        },
    }

    for site_key, site_record in site_map.items():
        drilldowns[f"project::site::{site_key}"] = {
            "title": f"Project Sample — {site_record.get('site_name', site_key)}",
            "reason": "These rows reflect the real project sample returned by the latest collector snapshot for this monitored site. Project-level last activity is not yet available in the current collector payload.",
            "atlassian_area": "Jira operational monitoring / project intelligence",
            "columns": ["project_key", "project_name", "project_type", "style", "simplified", "is_private"],
            "rows": site_record.get("project_rows", []),
        }

    return drilldowns