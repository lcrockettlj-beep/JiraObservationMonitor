from typing import Any, Dict, Iterable, Optional


HEALTHY_WORDS = {"ok", "healthy", "success", "available", "granted", "pass", "passed"}
WARNING_WORDS = {"warning", "partial", "limited", "degraded", "changed", "review"}
CRITICAL_WORDS = {"error", "failed", "failure", "denied", "unavailable", "missing", "critical"}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _contains_any(text: str, words: Iterable[str]) -> bool:
    return any(word in text for word in words)


def _extract_first(data: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _extract_permission_status(site: Dict[str, Any]) -> Optional[str]:
    permissions = site.get("permissions") or site.get("permission_checker") or site.get("mypermissions")

    if isinstance(permissions, dict):
        if "overall_status" in permissions:
            return str(permissions.get("overall_status"))
        if "status" in permissions:
            return str(permissions.get("status"))

        perms = permissions.get("permissions")
        if isinstance(perms, dict):
            denied = 0
            granted = 0

            for _, value in perms.items():
                granted_flag = False

                if isinstance(value, dict):
                    granted_flag = bool(value.get("havePermission") or value.get("granted"))
                elif isinstance(value, bool):
                    granted_flag = value

                if granted_flag:
                    granted += 1
                else:
                    denied += 1

            if denied > 0:
                return "warning"
            if granted > 0:
                return "ok"

    return None


def classify_state(site: Dict[str, Any]) -> str:
    """
    Classifies a site into:
    - critical
    - warning
    - stable

    This uses only real backend truth fields and does not invent risk
    thresholds from issue counts or project counts.
    """
    permission_status = _norm(_extract_permission_status(site))
    audit_status = _norm(_extract_first(site, ["audit_status"]))
    audit_api_access = _norm(_extract_first(site, ["audit_api_access"]))
    licence_status = _norm(_extract_first(site, ["licence_status", "license_status"]))
    licence_api_access = _norm(_extract_first(site, ["licence_api_access", "license_api_access"]))
    growth_status = _norm(_extract_first(site, ["growth_status"]))
    collected_at = _extract_first(site, ["collected_at", "snapshot_collected_at", "last_collected"])

    project_count = _safe_int(_extract_first(site, ["project_count", "projects_count"]))
    issue_count = _safe_int(_extract_first(site, ["issue_count", "issues_count"]))
    unresolved_issue_count = _safe_int(_extract_first(site, ["unresolved_issue_count"]))
    updated_last_7_days_count = _safe_int(_extract_first(site, ["updated_last_7_days_count"]))

    has_core_metrics = any(
        value is not None
        for value in [
            project_count,
            issue_count,
            unresolved_issue_count,
            updated_last_7_days_count,
        ]
    )

    critical_signals = [
        permission_status,
        audit_status,
        audit_api_access,
        licence_status,
        licence_api_access,
    ]

    if any(_contains_any(signal, CRITICAL_WORDS) for signal in critical_signals if signal):
        return "critical"

    if not collected_at and not has_core_metrics:
        return "critical"

    warning_signals = [
        permission_status,
        audit_status,
        audit_api_access,
        licence_status,
        licence_api_access,
        growth_status,
    ]

    if any(_contains_any(signal, WARNING_WORDS) for signal in warning_signals if signal):
        return "warning"

    remaining_seats = _safe_int(_extract_first(site, ["remaining_seats"]))
    if remaining_seats is not None and remaining_seats <= 0:
        return "warning"

    if not has_core_metrics:
        return "warning"

    return "stable"