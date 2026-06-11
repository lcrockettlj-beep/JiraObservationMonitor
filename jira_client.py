import os
import threading
import time

import requests
from requests.adapters import HTTPAdapter


ATLASSIAN_API_BASE = "https://api.atlassian.com"
REQUEST_TIMEOUT = int(os.getenv("JOM_REQUEST_TIMEOUT", "30"))
HTTP_POOL_SIZE = int(os.getenv("JOM_HTTP_POOL_SIZE", "20"))
RETRY_ATTEMPTS = int(os.getenv("JOM_RETRY_ATTEMPTS", "2"))
RETRY_BACKOFF_SECONDS = float(os.getenv("JOM_RETRY_BACKOFF_SECONDS", "0.6"))

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


def _classify_error(response=None, exc=None):
    status_code = None
    error_text = ""

    if response is not None:
        try:
            status_code = response.status_code
        except Exception:
            status_code = None

        try:
            error_text = (response.text or "").lower()
        except Exception:
            error_text = ""

    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"

    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection_error"

    if status_code == 401:
        return "auth_error"
    if status_code == 403:
        return "permission_limited"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    if status_code == 400:
        return "bad_request"
    if status_code is not None and 500 <= status_code <= 599:
        return "server_error"

    if "timeout" in error_text:
        return "timeout"
    if "forbidden" in error_text:
        return "permission_limited"
    if "not found" in error_text:
        return "not_found"
    if "rate limit" in error_text:
        return "rate_limited"

    if exc is not None:
        return "unknown_error"

    return "unknown_error"


def _is_retryable(error_category):
    return error_category in {
        "timeout",
        "connection_error",
        "rate_limited",
        "server_error",
        "transient_error"
    }


def _shape_error(exc, response=None, attempt_count=1):
    error_category = _classify_error(response=response, exc=exc)

    error_info = {
        "message": str(exc),
        "status_code": None,
        "url": None,
        "response_text": None,
        "error_category": error_category,
        "attempt_count": attempt_count,
        "retryable": _is_retryable(error_category)
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


def _request_json_once(method, url, access_token, params=None):
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
        "response": response
    }


def _request_json(method, url, access_token, params=None):
    last_error_info = None
    last_response = None

    total_attempts = RETRY_ATTEMPTS + 1

    for attempt_index in range(1, total_attempts + 1):
        try:
            result = _request_json_once(method, url, access_token, params=params)
            response = result["response"]

            return {
                "ok": True,
                "data": result["data"],
                "error": None,
                "error_detail": None,
                "status_code": response.status_code,
                "url": response.url,
                "attempt_count": attempt_index,
                "retryable": False,
                "error_category": None
            }

        except Exception as exc:
            response = None
            if hasattr(exc, "response"):
                response = exc.response

            error_info = _shape_error(exc, response=response, attempt_count=attempt_index)
            last_error_info = error_info
            last_response = response

            if error_info["retryable"] and attempt_index < total_attempts:
                sleep_seconds = RETRY_BACKOFF_SECONDS * attempt_index
                time.sleep(sleep_seconds)
                continue

            break

    return {
        "ok": False,
        "data": None,
        "error": last_error_info["message"] if last_error_info else "Unknown request error",
        "error_detail": last_error_info,
        "status_code": last_error_info["status_code"] if last_error_info else None,
        "url": last_error_info["url"] if last_error_info else url,
        "attempt_count": last_error_info["attempt_count"] if last_error_info else 1,
        "retryable": last_error_info["retryable"] if last_error_info else False,
        "error_category": last_error_info["error_category"] if last_error_info else "unknown_error"
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
        "cloud_id": cloud_id,
        "attempt_count": result.get("attempt_count", 1),
        "retryable": result.get("retryable", False),
        "error_category": result.get("error_category")
    }


def test_client_setup():
    return {
        "status": "ok",
        "message": "Stability-pack Jira client module loaded successfully",
        "base_url": ATLASSIAN_API_BASE,
        "timeout_seconds": REQUEST_TIMEOUT,
        "http_pool_size": HTTP_POOL_SIZE,
        "retry_attempts": RETRY_ATTEMPTS,
        "retry_backoff_seconds": RETRY_BACKOFF_SECONDS
    }
