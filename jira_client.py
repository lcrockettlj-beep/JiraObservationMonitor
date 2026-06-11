import requests

ATLASSIAN_API_BASE = "https://api.atlassian.com"
REQUEST_TIMEOUT = 30


def build_headers(access_token):
    if not access_token:
        raise ValueError("Access token is required")

    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }


def get_accessible_resources(access_token):
    url = f"{ATLASSIAN_API_BASE}/oauth/token/accessible-resources"
    response = requests.get(
        url,
        headers=build_headers(access_token),
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def jira_api_base(cloud_id):
    return f"{ATLASSIAN_API_BASE}/ex/jira/{cloud_id}/rest/api/3"


def jira_get(access_token, cloud_id, endpoint, params=None):
    url = f"{jira_api_base(cloud_id)}/{endpoint.lstrip('/')}"
    response = requests.get(
        url,
        headers=build_headers(access_token),
        params=params,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    if response.text.strip():
        return response.json()

    return {}


def safe_jira_get(access_token, cloud_id, endpoint, params=None):
    try:
        data = jira_get(access_token, cloud_id, endpoint, params=params)
        return {
            "ok": True,
            "data": data,
            "error": None
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": str(exc)
        }
