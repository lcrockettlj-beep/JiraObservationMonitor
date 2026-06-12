from typing import Any, Dict, Iterable, Optional


HEALTHY_WORDS = {
    "ok",
    "healthy",
    "success",
    "available",
    "granted",
    "pass",
    "passed",
    "stable",
}

WARNING_WORDS = {
    "warning",
    "partial",
    "limited",
    "degraded",
    "changed",
    "review",
    "permission_limited",
}

CRITICAL_WORDS = {
    "error",
    "failed",
    "failure",
    "denied",
    "unavailable",
    "missing",
    "critical",
}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _contains_any(text: str, words: Iterable[str]) -> bool:
    return any(word in text for word in words)


def _deep_first(data: Dict[str, Any], paths: Iterable[str]) -> Any:
    for path in paths:
        value = _deep_get(data, path)
        if value is not None:
            return value
    return None


def _deep_get(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict) and part in current:
            current = current.get(part)
        else:
            return None
    return current


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
    permission_checker = site.get("permission_checker") or _deep_first(
        site,
        ["permission_checker"],
    )

    if isinstance(permission_checker, dict):
        if permission_checker.get("available") is True:
            checked = permission_checker.get("permissions_checked", {})
            if isinstance(checked, dict) and checked:
                if all(bool(v) for v in checked.values()):
                    return "ok"
                return "warning"
            return "ok"

        if permission_checker.get("available") is False:
            return "warning"

    permissions = site.get("permissions") or site.get("mypermissions")
    if isinstance(permissions, dict):
        if "overall_status" in permissions:
            return str(permissions.get("overall_status"))
        if "status" in permissions:
            return str(permissions.get("status"))

    return None


def classify_state(site: Dict[str, Any]) -> str:
    """
    Classifies a site into:
    - critical
    - warning
    - stable

    IMPORTANT:
    1. Trust backend `status` first if present.
    2. Only fall back to derived logic if backend status is absent.
    """
    backend_status = _norm(_deep_first(site, ["status"]))

    if backend_status == "healthy":
        return "stable"
    if backend_status == "warning":
        return "warning"
    if backend_status == "critical":
        return "critical"

    permission_status = _norm(_extract_permission_status(site))
    audit_status = _norm(_deep_first(site, ["audit_status", "audit.audit_status"]))
    audit_api_access = _norm(
        _deep_first(site, ["audit_api_access", "audit.audit_api_access"])
    )
    licence_status = _norm(
        _deep_first(site, ["licence_status", "license_status", "licence.licence_status"])
    )
    licence_api_access = _norm(
        _deep_first(
            site,
            ["licence_api_access", "license_api_access", "licence.licence_api_access"],
        )
    )
    growth_status = _norm(_deep_first(site, ["growth_status", "snapshot.growth_status"]))
    collected_at = _deep_first(
        site,
        [
            "run_timestamp_local",
            "collected_at",
            "collected_at_utc",
            "snapshot_collected_at",
            "last_collected",
            "run_timestamp_utc",
        ],
    )

    project_count = _safe_int(_deep_first(site, ["project_count"]))
    issue_count = _safe_int(_deep_first(site, ["issue_count_total"]))
    unresolved_issue_count = _safe_int(_deep_first(site, ["issue_count_unresolved"]))
    updated_last_7_days_count = _safe_int(_deep_first(site, ["issue_count_updated_last_7d"]))

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

    remaining_seats = _safe_int(
        _deep_first(
            site,
            [
                "remaining_seats",
                "seats_remaining",
                "licence_summary.products.0.remaining_seats",
            ],
        )
    )
    if remaining_seats is not None and remaining_seats <= 0:
        return "warning"

    if not has_core_metrics:
        return "warning"

    return "stable"