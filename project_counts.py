
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
        "gli it project": "gli-it-project",
        "gli delivery tm": "gli-delivery-tm",
        "gli global technology": "gli-global-technology",
    }
    return mappings.get(text)


def load_project_counts_from_latest_run():
    file_name = "latest_run.json"

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

        site_key = _normalise_site_key_from_url(site.get("url"))
        if not site_key:
            site_key = _normalise_site_key_from_name(site.get("name"))
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
