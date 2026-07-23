from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "static" / "data"

NAMED_ACCESS_FILE = DATA_DIR / "live_named_access_contract"
USER_FOOTPRINT_FILE = DATA_DIR / "user_footprint.json"
SOURCE_RELIABILITY_FILE = DATA_DIR / "source_reliability_status.json"
SITE_REGISTRY_FILE = DATA_DIR / "site_registry.json"
OUTPUT_FILE = DATA_DIR / "admin_insights.json"


SEVERITY_ORDER = {
    "critical": 0,
    "risk": 1,
    "waste": 2,
    "drift": 3,
    "info": 4,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in (
            "users",
            "items",
            "records",
            "entries",
            "data",
            "results",
            "members",
            "accounts",
            "footprints",
        ):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def deep_find_lists(value: Any, path: str = "") -> list[tuple[str, list[Any]]]:
    found: list[tuple[str, list[Any]]] = []
    if isinstance(value, list):
        found.append((path, value))
    elif isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            found.extend(deep_find_lists(child, child_path))
    return found


def looks_like_user_record(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    keys = {str(k).lower() for k in record.keys()}
    identity_keys = {
        "accountid",
        "account_id",
        "user_id",
        "email",
        "emailaddress",
        "email_address",
        "displayname",
        "display_name",
        "name",
    }
    return bool(keys.intersection(identity_keys))


def collect_user_records(payload: Any) -> list[dict[str, Any]]:
    direct = as_list(payload)
    if direct and any(looks_like_user_record(x) for x in direct):
        return [x for x in direct if isinstance(x, dict)]

    candidates: list[dict[str, Any]] = []
    for _, list_value in deep_find_lists(payload):
        if list_value and any(looks_like_user_record(x) for x in list_value):
            candidates.extend([x for x in list_value if isinstance(x, dict)])

    deduped: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = user_key(item)
        if key:
            deduped[key] = merge_records(deduped.get(key, {}), item)
    return list(deduped.values())


def lower_get(record: dict[str, Any], *names: str) -> Any:
    lookup = {str(k).lower(): v for k, v in record.items()}
    for name in names:
        value = lookup.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def user_key(record: dict[str, Any]) -> str:
    value = lower_get(
        record,
        "account_id",
        "accountId",
        "accountid",
        "user_id",
        "userId",
        "email",
        "email_address",
        "emailAddress",
        "emailaddress",
        "display_name",
        "displayName",
        "name",
    )
    return str(value).strip().lower() if value not in (None, "") else ""


def display_name(record: dict[str, Any]) -> str:
    value = lower_get(record, "display_name", "displayName", "name", "email", "email_address", "account_id")
    return str(value).strip() if value not in (None, "") else "Unknown user"


def email_value(record: dict[str, Any]) -> str:
    value = lower_get(record, "email", "email_address", "emailAddress", "emailaddress")
    return str(value).strip() if value not in (None, "") else ""


def account_id_value(record: dict[str, Any]) -> str:
    value = lower_get(record, "account_id", "accountId", "accountid", "user_id", "userId")
    return str(value).strip() if value not in (None, "") else ""


def boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "active", "enabled"}:
        return True
    if text in {"false", "no", "n", "0", "inactive", "disabled"}:
        return False
    return None


def is_disabled(record: dict[str, Any]) -> bool:
    explicit_disabled = boolish(lower_get(record, "disabled", "is_disabled", "isDisabled"))
    if explicit_disabled is True:
        return True

    active = boolish(lower_get(record, "active", "is_active", "isActive", "account_active"))
    if active is False:
        return True

    status = lower_get(record, "status", "account_status", "accountStatus", "state")
    if status is not None:
        text = str(status).strip().lower()
        if text in {"disabled", "deactivated", "inactive", "suspended", "closed"}:
            return True

    return False


def has_product_access(record: dict[str, Any]) -> bool:
    for key in (
        "has_product_access",
        "hasProductAccess",
        "product_access",
        "productAccess",
        "access",
        "products",
        "sites",
        "application_roles",
        "applicationRoles",
        "groups",
    ):
        value = lower_get(record, key)
        if isinstance(value, list) and len(value) > 0:
            return True
        if isinstance(value, dict) and len(value) > 0:
            return True
        truth = boolish(value)
        if truth is True:
            return True

    access_count = lower_get(
        record,
        "access_count",
        "product_access_count",
        "productAccessCount",
        "group_count",
        "groups_count",
        "site_count",
    )
    try:
        if access_count is not None and int(access_count) > 0:
            return True
    except Exception:
        pass

    return False


def is_licensed(record: dict[str, Any]) -> bool:
    for key in (
        "licensed",
        "is_licensed",
        "isLicensed",
        "has_license",
        "hasLicense",
        "billing_seat",
        "billingSeat",
        "seat_consuming",
        "seatConsuming",
    ):
        value = lower_get(record, key)
        truth = boolish(value)
        if truth is True:
            return True
        if truth is False:
            continue

    seat_count = lower_get(record, "seat_count", "license_count", "licenses", "licensed_products")
    if isinstance(seat_count, list) and len(seat_count) > 0:
        return True
    try:
        if seat_count is not None and int(seat_count) > 0:
            return True
    except Exception:
        pass

    return False


def has_observable_license_signal(record: dict[str, Any]) -> bool:
    """
    Return True only when the loaded source record actually exposes a license/billing field.

    This prevents false positives where every user has product access but the current
    input schema simply does not include user-level billing/license data.
    """
    observable_keys = {
        "licensed",
        "is_licensed",
        "isLicensed",
        "has_license",
        "hasLicense",
        "billing_seat",
        "billingSeat",
        "seat_consuming",
        "seatConsuming",
        "seat_count",
        "license_count",
        "licenses",
        "licensed_products",
    }

    lower_keys = {str(k).lower() for k in record.keys()}
    return bool({k.lower() for k in observable_keys}.intersection(lower_keys))

def inactive_hint(record: dict[str, Any]) -> bool:
    status = lower_get(record, "usage_status", "activity_status", "activityStatus", "last_active_status")
    if status is not None and str(status).strip().lower() in {"inactive", "unused", "stale", "never_accessed"}:
        return True

    days = lower_get(record, "days_inactive", "inactive_days", "daysSinceLastActive", "days_since_last_active")
    try:
        if days is not None and int(days) >= 90:
            return True
    except Exception:
        pass

    last_active = lower_get(record, "last_active", "lastActive", "last_seen", "lastSeen")
    if last_active is not None and str(last_active).strip().lower() in {"never", "none", "null", "unknown"}:
        return True

    return False


def source_name(record: dict[str, Any]) -> str:
    value = lower_get(record, "source", "source_name", "sourceName", "origin")
    return str(value).strip() if value not in (None, "") else "unknown"


def site_value(record: dict[str, Any]) -> str:
    value = lower_get(record, "site", "site_key", "siteKey", "cloud_id", "cloudId", "tenant")
    return str(value).strip() if value not in (None, "") else ""


def merge_records(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    sources = set()

    for original in (left, right):
        existing_source = source_name(original)
        if existing_source != "unknown":
            sources.add(existing_source)

    for key, value in right.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value

    if sources:
        merged["_merged_sources"] = sorted(sources)

    return merged


def build_user_index(named_access: Any, user_footprint: Any) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    for record in collect_user_records(named_access):
        key = user_key(record)
        if not key:
            continue
        enriched = dict(record)
        enriched["_seen_in_named_access_truth_v2"] = True
        enriched["_source_file_named_access_truth_v2"] = True
        index[key] = merge_records(index.get(key, {}), enriched)

    for record in collect_user_records(user_footprint):
        key = user_key(record)
        if not key:
            continue
        enriched = dict(record)
        enriched["_seen_in_user_footprint"] = True
        enriched["_source_file_user_footprint"] = True
        index[key] = merge_records(index.get(key, {}), enriched)

    return index


def issue_record(
    *,
    category: str,
    severity: str,
    user: dict[str, Any],
    reason: str,
    action: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "user_key": user_key(user),
        "account_id": account_id_value(user),
        "display_name": display_name(user),
        "email": email_value(user),
        "site": site_value(user),
        "reason": reason,
        "recommended_action": action,
        "source_files": {
            "named_access_truth_v2": bool(user.get("_source_file_named_access_truth_v2")),
            "user_footprint": bool(user.get("_source_file_user_footprint")),
        },
        "evidence": evidence or {},
    }


def extract_source_reliability(source_reliability: Any) -> dict[str, Any]:
    if not isinstance(source_reliability, dict):
        return {
            "status": "unknown",
            "issue_count": None,
            "reason": "source_reliability_status.json is missing or not a JSON object",
        }

    status = (
        source_reliability.get("status")
        or source_reliability.get("overall_status")
        or source_reliability.get("source_reliability_status")
        or "unknown"
    )

    issue_count = (
        source_reliability.get("issue_count")
        or source_reliability.get("issues")
        or source_reliability.get("error_count")
    )

    if isinstance(issue_count, list):
        issue_count = len(issue_count)

    return {
        "status": status,
        "issue_count": issue_count,
        "reason": "source reliability file loaded",
    }


def extract_registry_summary(site_registry: Any) -> dict[str, Any]:
    if not isinstance(site_registry, dict):
        return {
            "status": "unknown",
            "monitored_sites": [],
            "unmonitored_sites": [],
        }

    monitored: list[str] = []
    unmonitored: list[str] = []

    for _, list_value in deep_find_lists(site_registry):
        for item in list_value:
            if not isinstance(item, dict):
                continue
            site = lower_get(item, "site", "site_key", "siteKey", "key", "name", "url")
            if not site:
                continue

            state = str(lower_get(item, "status", "state", "classification", "monitoring_status") or "").lower()
            approved = boolish(lower_get(item, "approved", "monitored", "is_monitored", "isMonitored"))

            if approved is True or state in {"approved", "monitored", "active"}:
                monitored.append(str(site))
            elif approved is False or state in {"discovered", "unmonitored", "ignored", "pending"}:
                unmonitored.append(str(site))

    return {
        "status": "loaded",
        "monitored_sites": sorted(set(monitored)),
        "unmonitored_sites": sorted(set(unmonitored)),
    }


def field_exists_anywhere(records: list[dict[str, Any]], field_names: set[str]) -> bool:
    wanted = {name.lower() for name in field_names}
    for record in records:
        if not isinstance(record, dict):
            continue
        keys = {str(k).lower() for k in record.keys()}
        if keys.intersection(wanted):
            return True
    return False


def build_source_capabilities(users: dict[str, dict[str, Any]]) -> dict[str, Any]:
    records = list(users.values())

    license_fields = {
        "licensed",
        "is_licensed",
        "isLicensed",
        "has_license",
        "hasLicense",
        "billing_seat",
        "billingSeat",
        "seat_consuming",
        "seatConsuming",
        "seat_count",
        "license_count",
        "licenses",
        "licensed_products",
    }

    disabled_fields = {
        "disabled",
        "is_disabled",
        "isDisabled",
        "active",
        "is_active",
        "isActive",
        "account_active",
        "status",
        "account_status",
        "accountStatus",
        "state",
    }

    activity_fields = {
        "usage_status",
        "activity_status",
        "activityStatus",
        "last_active_status",
        "days_inactive",
        "inactive_days",
        "daysSinceLastActive",
        "days_since_last_active",
        "last_active",
        "lastActive",
        "last_seen",
        "lastSeen",
    }

    access_fields = {
        "has_product_access",
        "hasProductAccess",
        "product_access",
        "productAccess",
        "access",
        "products",
        "sites",
        "application_roles",
        "applicationRoles",
        "groups",
        "access_count",
        "product_access_count",
        "productAccessCount",
        "group_count",
        "groups_count",
        "site_count",
        "product_access_assignments",
    }

    license_available = field_exists_anywhere(records, license_fields)
    disabled_available = field_exists_anywhere(records, disabled_fields)
    activity_available = field_exists_anywhere(records, activity_fields)
    access_available = field_exists_anywhere(records, access_fields)

    return {
        "user_records_evaluated": len(records),
        "access_detection_available": access_available,
        "license_detection_available": license_available,
        "disabled_detection_available": disabled_available,
        "activity_detection_available": activity_available,
        "source_mismatch_detection_available": True,
        "suppressed_categories": {
            "access_without_license_signal": not license_available,
            "licensed_inactive_or_unused": not (license_available and activity_available),
            "disabled_with_access": not (disabled_available and access_available),
        },
        "capability_notes": [
            "Capability flags are derived from observed fields in live_named_access_contract and user_footprint.json.",
            "Suppressed categories should not be interpreted as zero confirmed issues.",
            "A suppressed category means the loaded source schema does not expose enough user-level fields to make that judgement safely.",
        ],
    }

def build_insights(
    named_access: Any,
    user_footprint: Any,
    source_reliability: Any,
    site_registry: Any,
) -> dict[str, Any]:
    users = build_user_index(named_access, user_footprint)
    capabilities = build_source_capabilities(users)

    categories: dict[str, list[dict[str, Any]]] = {
        "disabled_with_access": [],
        "access_without_license_signal": [],
        "licensed_inactive_or_unused": [],
        "source_mismatch_users": [],
    }

    for _, user in sorted(users.items(), key=lambda pair: display_name(pair[1]).lower()):
        disabled = is_disabled(user)
        access = has_product_access(user)
        licensed = is_licensed(user)
        inactive = inactive_hint(user)

        seen_named = bool(user.get("_seen_in_named_access_truth_v2"))
        seen_footprint = bool(user.get("_seen_in_user_footprint"))

        evidence = {
            "disabled": disabled,
            "has_product_access_signal": access,
            "has_license_signal": licensed,
            "has_observable_license_signal": has_observable_license_signal(user),
            "inactive_signal": inactive,
            "seen_in_named_access_truth_v2": seen_named,
            "seen_in_user_footprint": seen_footprint,
            "merged_sources": user.get("_merged_sources", []),
        }

        if disabled and access:
            categories["disabled_with_access"].append(
                issue_record(
                    category="disabled_with_access",
                    severity="critical",
                    user=user,
                    reason="User appears disabled or inactive but still has product/group/site access signals.",
                    action="Review the user in Atlassian Admin Directory and remove product/group access if no longer required.",
                    evidence=evidence,
                )
            )

        if access and has_observable_license_signal(user) and not licensed:
            categories["access_without_license_signal"].append(
                issue_record(
                    category="access_without_license_signal",
                    severity="risk",
                    user=user,
                    reason="User has product/access signals but no clear license or billing-seat signal was found in the loaded truth data.",
                    action="Check Atlassian Admin product access and billing seat allocation for this account.",
                    evidence=evidence,
                )
            )

        if licensed and inactive:
            categories["licensed_inactive_or_unused"].append(
                issue_record(
                    category="licensed_inactive_or_unused",
                    severity="waste",
                    user=user,
                    reason="User appears licensed or seat-consuming but has inactive, stale, or never-active usage signals.",
                    action="Confirm whether this user still needs product access; reclaim license if no longer required.",
                    evidence=evidence,
                )
            )

        if seen_named != seen_footprint:
            categories["source_mismatch_users"].append(
                issue_record(
                    category="source_mismatch_users",
                    severity="drift",
                    user=user,
                    reason="User appears in one admin/access source but not the other, indicating possible source drift or incomplete collection.",
                    action="Refresh named access truth and user footprint sources, then re-check reconciliation.",
                    evidence=evidence,
                )
            )

    summary = {
        "critical": len(categories["disabled_with_access"]),
        "risk": len(categories["access_without_license_signal"]),
        "waste": len(categories["licensed_inactive_or_unused"]),
        "drift": len(categories["source_mismatch_users"]),
        "total_issues": sum(len(items) for items in categories.values()),
        "user_records_evaluated": len(users),
    }

    category_meta = {
        "disabled_with_access": {
            "severity": "critical",
            "title": "Disabled users with access",
            "description": "Accounts that appear disabled/inactive while still showing product access signals.",
        },
        "access_without_license_signal": {
            "severity": "risk",
            "title": "Access without clear license signal",
            "description": "Accounts with product access signals and explicit license/billing fields showing no license. Suppressed when source files do not expose license fields.",
        },
        "licensed_inactive_or_unused": {
            "severity": "waste",
            "title": "Licensed inactive or unused users",
            "description": "Accounts that appear licensed but inactive, stale, or never active.",
        },
        "source_mismatch_users": {
            "severity": "drift",
            "title": "Source mismatch users",
            "description": "Accounts present in one source but absent from another.",
        },
    }

    return {
        "schema": "jom.admin_insights.v1",
        "generated_at_utc": utc_now_iso(),
        "mode": "backend_only_no_ui",
        "source_files": {
            "named_access_truth_v2": str(NAMED_ACCESS_FILE.relative_to(ROOT)),
            "user_footprint": str(USER_FOOTPRINT_FILE.relative_to(ROOT)),
            "source_reliability_status": str(SOURCE_RELIABILITY_FILE.relative_to(ROOT)),
            "site_registry": str(SITE_REGISTRY_FILE.relative_to(ROOT)),
        },
        "capabilities": capabilities,
        "source_health": {
            "source_reliability": extract_source_reliability(source_reliability),
            "site_registry": extract_registry_summary(site_registry),
        },
        "summary": summary,
        "category_meta": category_meta,
        "categories": {
            key: sorted(
                value,
                key=lambda item: (
                    SEVERITY_ORDER.get(str(item.get("severity")), 99),
                    str(item.get("display_name", "")).lower(),
                ),
            )
            for key, value in categories.items()
        },
        "notes": [
            "Admin Insight Engine v1 is backend/data only. No UI wiring has been performed.",
            "Issue detection is intentionally conservative and based only on fields present in the loaded JSON sources.",
            "If counts are zero, this may mean the environment is healthy or that source files do not yet expose the required signals.",
            "User-level license risk detection is suppressed unless source records expose explicit license or billing-seat fields.",
            "Capability metadata is backend-only and intended to prevent the UI from presenting unavailable checks as clean results.",
        ],
    }


def main() -> int:
    named_access = read_json(NAMED_ACCESS_FILE, {})
    user_footprint = read_json(USER_FOOTPRINT_FILE, {})
    source_reliability = read_json(SOURCE_RELIABILITY_FILE, {})
    site_registry = read_json(SITE_REGISTRY_FILE, {})

    payload = build_insights(
        named_access=named_access,
        user_footprint=user_footprint,
        source_reliability=source_reliability,
        site_registry=site_registry,
    )

    write_json(OUTPUT_FILE, payload)

    summary = payload.get("summary", {})
    print("Admin Insight Engine v1 complete")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Users evaluated: {summary.get('user_records_evaluated')}")
    print(f"Total issues: {summary.get('total_issues')}")
    print(f"Critical: {summary.get('critical')}")
    print(f"Risk: {summary.get('risk')}")
    print(f"Waste: {summary.get('waste')}")
    print(f"Drift: {summary.get('drift')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())



