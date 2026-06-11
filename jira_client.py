import os
import threading

import requests
from requests.adapters import HTTPAdapter


ATLASSIAN_API_BASE = "https://api.atlassian.com"
REQUEST_TIMEOUT = int(os.getenv("JOM_REQUEST_TIMEOUT", "30"))
HTTP_POOL_SIZE = int(os.getenv("JOM_HTTP_POOL_SIZE", "20"))

_thread_local = threading.local()


def build_headers(access_token):
    if not access_token:
        raise ValueError("Access token is required")

    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }


def _get_session():
    session = getattr(_thread_local, "session", None)

    if session is None:
        session = requests.Session()

        adapter = HTTPAdapter(
            pool_connections=HTTP_POOL_SIZE,
            pool_maxsize=HTTP_POOL_SIZE
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        _thread_local.session = session

    return session


def _safe_text(response):
    try:
        return response.text.strip()
    except Exception:
        return ""


def _parse_json_response(response):
    text = _safe_text(response)

    if not text:
        return {}

    return response.json()


def _shape_error(exc, response=None):
    error_info = {
        "message": str(exc),
        "status_code": None,
        "url": None,
        "response_text": None
    }

    if response is not None:
        try:
            error_info["status_code"] = response.status_code
        except Exception:
            pass

        try:
            error_info["url"] = response.url
        except Exception:
            pass

        try:
            error_info["response_text"] = response.text[:1000] if response.text else None
        except Exception:
            pass

    return error_info


def _request_json(method, url, access_token, params=None):
    response = None

    try:
        session = _get_session()

        response = session.request(
            method=method,
            url=url,
            headers=build_headers(access_token),
            params=params,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()
        data = _parse_json_response(response)

        return {
            "ok": True,
            "data": data,
            "error": None,
            "error_detail": None,
            "status_code": response.status_code,
            "url": response.url
        }

    except Exception as exc:
        error_info = _shape_error(exc, response=response)

        return {
            "ok": False,
            "data": None,
            "error": error_info["message"],
            "error_detail": error_info,
            "status_code": error_info["status_code"],
            "url": error_info["url"]
        }


def get_accessible_resources(access_token):
    url = f"{ATLASSIAN_API_BASE}/oauth/token/accessible-resources"
    result = _request_json("GET", url, access_token)

    if not result["ok"]:
        raise RuntimeError(
            f"Failed to fetch accessible resources: {result['error']}"
        )

    return result["data"]


def safe_get_accessible_resources(access_token):
    url = f"{ATLASSIAN_API_BASE}/oauth/token/accessible-resources"
    return _request_json("GET", url, access_token)


def jira_api_base(cloud_id):
    if not cloud_id:
        raise ValueError("cloud_id is required")

    return f"{ATLASSIAN_API_BASE}/ex/jira/{cloud_id}/rest/api/3"


def jira_url(cloud_id, endpoint):
    endpoint_clean = str(endpoint).lstrip("/")
    return f"{jira_api_base(cloud_id)}/{endpoint_clean}"


def jira_get(access_token, cloud_id, endpoint, params=None):
    url = jira_url(cloud_id, endpoint)
    result = _request_json("GET", url, access_token, params=params)

    if not result["ok"]:
        raise RuntimeError(
            f"Jira GET failed for '{endpoint}': {result['error']}"
        )

    return result["data"]


def safe_jira_get(access_token, cloud_id, endpoint, params=None):
    url = jira_url(cloud_id, endpoint)
    result = _request_json("GET", url, access_token, params=params)

    return {
        "ok": result["ok"],
        "data": result["data"],
        "error": result["error"],
        "error_detail": result.get("error_detail"),
        "status_code": result.get("status_code"),
        "url": result.get("url"),
        "endpoint": endpoint,
        "cloud_id": cloud_id
    }


def test_client_setup():
    return {
        "status": "ok",
        "message": "Performance-optimised Jira client module loaded successfully",
        "base_url": ATLASSIAN_API_BASE,
        "timeout_seconds": REQUEST_TIMEOUT,
        "http_pool_size": HTTP_POOL_SIZE
    }