from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from auth import get_valid_access_token, get_accessible_jira_resources

API_ROOT = "https://api.atlassian.com/ex/jira"
DEFAULT_TIMEOUT = int(os.getenv("JOM_REQUEST_TIMEOUT", "30") or 30)
DEFAULT_RETRY_ATTEMPTS = int(os.getenv("JOM_RETRY_ATTEMPTS", "2") or 2)
DEFAULT_RETRY_BACKOFF = float(os.getenv("JOM_RETRY_BACKOFF_SECONDS", "0.6") or 0.6)
DEFAULT_PERMISSIONS_QUERY = os.getenv("JOM_PERMISSIONS_QUERY", "BROWSE_PROJECTS")
DEFAULT_SEARCH_MAX_RESULTS = int(os.getenv("JOM_SEARCH_MAX_RESULTS", "1") or 1)


class JiraApiClient:
    def __init__(self, access_token: Optional[str] = None) -> None:
        self.access_token = access_token or get_valid_access_token()
        self.timeout = DEFAULT_TIMEOUT
        self.retry_attempts = DEFAULT_RETRY_ATTEMPTS
        self.retry_backoff = DEFAULT_RETRY_BACKOFF
        self.search_max_results = max(1, min(DEFAULT_SEARCH_MAX_RESULTS, 5000))

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _request_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"

        last_error: Optional[str] = None
        for attempt in range(self.retry_attempts + 1):
            req = urllib.request.Request(url=url, headers=self._headers(), method="GET")
            started = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    elapsed = round(time.time() - started, 3)
                    return {
                        "ok": True,
                        "status_code": getattr(response, "status", 200),
                        "elapsed_seconds": elapsed,
                        "data": json.loads(raw) if raw else {},
                        "url": url,
                    }
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {exc.code}: {raw}"
                if exc.code in (400, 401, 403, 404, 410):
                    return {
                        "ok": False,
                        "status_code": exc.code,
                        "elapsed_seconds": round(time.time() - started, 3),
                        "error": last_error,
                        "url": url,
                    }
            except urllib.error.URLError as exc:
                last_error = f"Network error: {exc}"
            except Exception as exc:
                last_error = f"Unexpected error: {exc}"

            if attempt < self.retry_attempts:
                time.sleep(self.retry_backoff * (attempt + 1))

        return {
            "ok": False,
            "status_code": 0,
            "elapsed_seconds": 0,
            "error": last_error or "Unknown error",
            "url": url,
        }

    def request_jira(self, cloud_id: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        path = path if path.startswith("/") else f"/{path}"
        url = f"{API_ROOT}/{cloud_id}{path}"
        return self._request_json(url, params=params)

    def list_accessible_resources(self) -> List[Dict[str, Any]]:
        return get_accessible_jira_resources(self.access_token)

    def get_server_info(self, cloud_id: str) -> Dict[str, Any]:
        return self.request_jira(cloud_id, "/rest/api/3/serverInfo")

    def get_myself(self, cloud_id: str) -> Dict[str, Any]:
        return self.request_jira(cloud_id, "/rest/api/3/myself")

    def get_my_permissions(self, cloud_id: str, permissions: Optional[str] = None) -> Dict[str, Any]:
        permissions_value = permissions or DEFAULT_PERMISSIONS_QUERY
        return self.request_jira(
            cloud_id,
            "/rest/api/3/mypermissions",
            params={"permissions": permissions_value},
        )

    def get_projects(self, cloud_id: str) -> Dict[str, Any]:
        start_at = 0
        max_results = 50
        all_projects: List[Dict[str, Any]] = []
        elapsed_total = 0.0

        while True:
            result = self.request_jira(
                cloud_id,
                "/rest/api/3/project/search",
                params={"startAt": start_at, "maxResults": max_results},
            )
            elapsed_total += float(result.get("elapsed_seconds", 0) or 0)
            if not result.get("ok"):
                result["elapsed_seconds"] = round(elapsed_total, 3)
                return result

            data = result.get("data", {}) or {}
            values = data.get("values", []) or []
            all_projects.extend(values)
            is_last = bool(data.get("isLast", True))
            if is_last or not values:
                return {
                    "ok": True,
                    "status_code": result.get("status_code", 200),
                    "elapsed_seconds": round(elapsed_total, 3),
                    "data": all_projects,
                    "url": result.get("url", ""),
                }
            start_at += len(values)

    def search_issue_count(self, cloud_id: str, jql: str) -> Dict[str, Any]:
        result = self.request_jira(
            cloud_id,
            "/rest/api/3/search/jql",
            params={
                "jql": jql,
                "maxResults": self.search_max_results,
                "fields": "none",
                "validateQuery": "strict",
            },
        )
        if not result.get("ok"):
            return result
        data = result.get("data", {}) or {}
        return {
            "ok": True,
            "status_code": result.get("status_code", 200),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "data": {"total": int(data.get("total", 0) or 0)},
            "url": result.get("url", ""),
        }

    def get_application_roles(self, cloud_id: str) -> Dict[str, Any]:
        return self.request_jira(cloud_id, "/rest/api/3/applicationrole")

    def get_audit_records(self, cloud_id: str, max_results: int = 20) -> Dict[str, Any]:
        return self.request_jira(
            cloud_id,
            "/rest/api/3/auditing/record",
            params={"maxResults": max_results},
        )
