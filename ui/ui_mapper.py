import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ui.view_models import (
    AuditRecordSampleViewModel,
    BillingSummaryViewModel,
    HomepageSummaryViewModel,
    HomepageViewModel,
    SiteAuditViewModel,
    SiteCardViewModel,
    SiteLicenceViewModel,
    SiteMetricViewModel,
    SitePermissionsViewModel,
    SiteProjectSampleViewModel,
    SiteServerInfoViewModel,
    SiteSnapshotDeltaViewModel,
    SiteSnapshotViewModel,
    SiteUsersViewModel,
)
from ui.ui_status import classify_state

ACTIVE_SITE_URLS = {
    "https://gli-global-technology.atlassian.net",
    "https://gli-delivery-tm.atlassian.net",
    "https://gli-it-project.atlassian.net",
}

EXCLUDED_SITE_TOKENS = {
    "gli-usa",
    "gaminglabs-team-tsyfo716",
    "gaminglabs-team-h2pbpmis",
}

BILLING_TRUTH: Dict[str, Dict[str, Optional[str]]] = {
    "https://gli-global-technology.atlassian.net": {
        "billing_cycle": "monthly",
        "next_bill_date": "Jul 03, 2026",
        "next_price_estimate": "USD 479.65",
    },
    "https://gli-delivery-tm.atlassian.net": {
        "billing_cycle": "annual",
        "next_bill_date": "Nov 08, 2026",
        "next_price_estimate": "(termed)",
    },
    "https://gli-it-project.atlassian.net": {
        "billing_cycle": None,
        "next_bill_date": None,
        "next_price_estimate": None,
    },
}


def load_latest_backend_payload(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    root = Path(base_dir or Path.cwd())

    best_payload = {"collected_at": None, "sites": []}
    best_dt: Optional[datetime] = None

    for file_name in ["latest_run.json", "latest_run_pretty.json"]:
        path = root / file_name
        if not path.exists():
            continue

        try:
            with path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
        except Exception:
            continue

        payload = normalize_backend_payload(raw)
        candidate_ts = payload.get("collected_at")
        candidate_dt = _parse_datetime(candidate_ts)

        if best_dt is None:
            best_payload = payload
            best_dt = candidate_dt
            continue

        if candidate_dt is not None and (best_dt is None or candidate_dt > best_dt):
            best_payload = payload
            best_dt = candidate_dt

    return best_payload


def normalize_backend_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {"collected_at": None, "sites": []}

    collected_at = (
        raw.get("run_timestamp_local")
        or raw.get("collected_at")
        or raw.get("snapshot_collected_at")
        or raw.get("generated_at")
        or raw.get("run_timestamp_utc")
        or _deep_get(raw, "raw_collection_summary.collected_at_utc")
    )

    raw_sites = raw.get("sites")
    if isinstance(raw_sites, list):
        sites = [site for site in raw_sites if isinstance(site, dict)]
    elif isinstance(raw_sites, dict):
        sites = [value for value in raw_sites.values() if isinstance(value, dict)]
    else:
        sites = []

    return {
        "collected_at": collected_at,
        "sites": sites,
    }


def build_homepage_view_model(base_dir: Optional[Path] = None) -> HomepageViewModel:
    payload = load_latest_backend_payload(base_dir=base_dir)
    all_sites = payload.get("sites", [])
    active_sites = [site for site in all_sites if _is_active_operational_site(site)]

    cards = [
        _build_site_card(site, fallback_collected_at=payload.get("collected_at"))
        for site in active_sites
    ]
    cards.sort(key=lambda card: card.site_name.lower())

    critical_sites = [card for card in cards if card.status == "critical"]
    warning_sites = [card for card in cards if card.status == "warning"]
    stable_sites = [card for card in cards if card.status == "stable"]

    collected_at = _pick_latest_collected_at(cards, payload.get("collected_at"))

    summary = HomepageSummaryViewModel(
        active_site_count=len(cards),
        critical_count=len(critical_sites),
        warning_count=len(warning_sites),
        stable_count=len(stable_sites),
        total_projects=sum(card.metrics.project_count for card in cards),
        total_issues=sum(card.metrics.issue_count for card in cards),
        total_unresolved=sum(card.metrics.unresolved_issue_count for card in cards),
        total_updated_last_7_days=sum(
            card.metrics.updated_last_7_days_count for card in cards
        ),
    )

    site_tabs = [
        {
            "site_key": card.site_key,
            "site_name": card.site_name,
            "site_url": card.site_url,
        }
        for card in cards
    ]

    return HomepageViewModel(
        collected_at=collected_at,
        active_site_count=len(cards),
        summary=summary,
        critical_sites=critical_sites,
        warning_sites=warning_sites,
        stable_sites=stable_sites,
        site_tabs=site_tabs,
    )


def _build_site_card(
    site: Dict[str, Any],
    fallback_collected_at: Optional[str],
) -> SiteCardViewModel:
    site_url = _extract_site_url(site)
    site_name = _extract_site_name(site, site_url)
    site_key = _slugify_site_name(site_name)

    metrics = SiteMetricViewModel(
        project_count=_safe_int(_deep_first(site, ["project_count"])) or 0,
        issue_count=_safe_int(_deep_first(site, ["issue_count_total"])) or 0,
        unresolved_issue_count=_safe_int(_deep_first(site, ["issue_count_unresolved"])) or 0,
        updated_last_7_days_count=_safe_int(_deep_first(site, ["issue_count_updated_last_7d"])) or 0,
    )

    users = _extract_site_users(site)

    licensed_users_estimate, seats, remaining_seats = _extract_licence_numbers(site)

    licence = SiteLicenceViewModel(
        licensed_users_estimate=licensed_users_estimate,
        seats=seats,
        remaining_seats=remaining_seats,
        licence_status=_as_str(_deep_first(site, ["licence_status"])),
        licence_api_access=_bool_to_status(_deep_first(site, ["licence_api_access"])),
    )

    audit = SiteAuditViewModel(
        audit_status=_as_str(_deep_first(site, ["audit_status"])),
        audit_api_access=_bool_to_status(_deep_first(site, ["audit_api_access"])),
        record_count=_safe_int(_deep_first(site, ["audit_summary.record_count"])),
        automation_related_record_count=_safe_int(
            _deep_first(site, ["audit_summary.automation_related_record_count"])
        ),
        category_counts=_extract_category_counts(site),
        records_sample=_extract_audit_records_sample(site),
    )

    permissions = _extract_permissions_view_model(site)

    collected_at_raw = (
        _as_str(
            _deep_first(
                site,
                [
                    "collected_at_utc",
                    "run_timestamp_utc",
                    "raw_collection_summary.collected_at_utc",
                    "run_timestamp_local",
                    "collected_at",
                    "snapshot_collected_at",
                    "last_collected",
                ],
            )
        )
        or fallback_collected_at
    )

    snapshot_delta = SiteSnapshotDeltaViewModel(
        snapshot_baseline=bool(_deep_first(site, ["snapshot_baseline"])),
        project_count_delta=_safe_int(_deep_first(site, ["project_count_delta"])),
        total_users_delta=_safe_int(_deep_first(site, ["total_users_delta"])),
        active_users_delta=_safe_int(_deep_first(site, ["active_users_delta"])),
        inactive_users_delta=_safe_int(_deep_first(site, ["inactive_users_delta"])),
        licensed_users_estimate_delta=_safe_int(_deep_first(site, ["licensed_users_estimate_delta"])),
        issue_count_total_delta=_safe_int(_deep_first(site, ["issue_count_total_delta"])),
        issue_count_unresolved_delta=_safe_int(_deep_first(site, ["issue_count_unresolved_delta"])),
    )

    delta_available = any(
        value is not None
        for value in [
            snapshot_delta.project_count_delta,
            snapshot_delta.total_users_delta,
            snapshot_delta.active_users_delta,
            snapshot_delta.inactive_users_delta,
            snapshot_delta.licensed_users_estimate_delta,
            snapshot_delta.issue_count_total_delta,
            snapshot_delta.issue_count_unresolved_delta,
        ]
    )

    snapshot = SiteSnapshotViewModel(
        collected_at=_format_timestamp_for_ui(collected_at_raw),
        growth_status=_as_str(_deep_first(site, ["growth_status"])),
        delta_available=delta_available,
        delta=snapshot_delta,
    )

    billing_truth = BILLING_TRUTH.get(site_url, {})
    billing_summary = BillingSummaryViewModel(
        billing_cycle=billing_truth.get("billing_cycle"),
        next_bill_date=billing_truth.get("next_bill_date"),
        next_price_estimate=billing_truth.get("next_price_estimate"),
    )

    server_info = SiteServerInfoViewModel(
        server_title=_as_str(_deep_first(site, ["server_info.server_title"])),
        deployment_type=_as_str(_deep_first(site, ["server_info.deployment_type"])),
        version=_as_str(_deep_first(site, ["server_info.version"])),
        default_locale=_as_str(_deep_first(site, ["server_info.default_locale"])),
        server_time_zone=_as_str(_deep_first(site, ["server_info.server_time_zone"])),
        display_url=_as_str(_deep_first(site, ["server_info.display_url"])),
    )

    project_sample = _extract_project_sample(site)

    usage_percent = _compute_usage_percent(
        licence.licensed_users_estimate,
        licence.seats,
    )

    return SiteCardViewModel(
        site_key=site_key,
        site_name=site_name,
        site_url=site_url,
        status=classify_state(site),
        metrics=metrics,
        users=users,
        licence=licence,
        audit=audit,
        permissions=permissions,
        snapshot=snapshot,
        billing_summary=billing_summary,
        server_info=server_info,
        project_sample=project_sample,
        usage_percent=usage_percent,
        last_collected=_format_timestamp_for_ui(collected_at_raw),
    )


def _extract_site_users(site: Dict[str, Any]) -> SiteUsersViewModel:
    """
    Site-level user display must use only users with access to the site.
    Do NOT show estate-wide total_users on a site card/page.
    """
    site_access_total = _extract_site_access_total(site)

    return SiteUsersViewModel(
        total_users=site_access_total,
        active_users=None,
        inactive_users=None,
    )


def _extract_site_access_total(site: Dict[str, Any]) -> Optional[int]:
    direct_estimate = _safe_int(_deep_first(site, ["licence_summary.licensed_users_estimate"]))
    if direct_estimate is not None:
        return direct_estimate

    licence_products = _deep_first(site, ["licence_summary.products"])
    if isinstance(licence_products, list):
        for product in licence_products:
            if isinstance(product, dict):
                user_count = _safe_int(product.get("user_count"))
                if user_count is not None:
                    return user_count

    app_role_sample = _deep_first(site, ["application_role_sample"])
    if isinstance(app_role_sample, list):
        for role in app_role_sample:
            if isinstance(role, dict):
                user_count = _safe_int(role.get("user_count"))
                if user_count is not None:
                    return user_count

    return None


def _extract_licence_numbers(site: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    licensed_users_estimate = _safe_int(
        _deep_first(site, ["licence_summary.licensed_users_estimate"])
    )

    product_candidates: List[Dict[str, Any]] = []

    licence_products = _deep_first(site, ["licence_summary.products"])
    if isinstance(licence_products, list):
        product_candidates.extend([item for item in licence_products if isinstance(item, dict)])

    app_role_sample = _deep_first(site, ["application_role_sample"])
    if isinstance(app_role_sample, list):
        product_candidates.extend([item for item in app_role_sample if isinstance(item, dict)])

    seats = None
    remaining_seats = None

    for item in product_candidates:
        if seats is None:
            seats = _safe_int(item.get("number_of_seats"))
        if remaining_seats is None:
            remaining_seats = _safe_int(item.get("remaining_seats"))
        if licensed_users_estimate is None:
            licensed_users_estimate = _safe_int(item.get("user_count"))

        if licensed_users_estimate is not None and seats is not None:
            break

    return licensed_users_estimate, seats, remaining_seats


def _extract_permissions_view_model(site: Dict[str, Any]) -> SitePermissionsViewModel:
    permission_checker = _deep_first(site, ["permission_checker"])
    if not isinstance(permission_checker, dict):
        return SitePermissionsViewModel()

    permissions_checked = permission_checker.get("permissions_checked", {})
    if not isinstance(permissions_checked, dict):
        permissions_checked = {}

    total_count = len(permissions_checked)
    granted_count = sum(1 for value in permissions_checked.values() if bool(value))
    denied_count = total_count - granted_count

    overall_status = "ok" if permission_checker.get("available") else "warning"
    if denied_count > 0:
        overall_status = "warning"

    return SitePermissionsViewModel(
        overall_status=overall_status,
        granted_count=granted_count,
        denied_count=denied_count,
        total_count=total_count,
    )


def _extract_project_sample(site: Dict[str, Any]) -> List[SiteProjectSampleViewModel]:
    sample = _deep_first(site, ["project_sample"])
    if not isinstance(sample, list):
        return []

    projects: List[SiteProjectSampleViewModel] = []
    for project in sample[:20]:
        if not isinstance(project, dict):
            continue

        projects.append(
            SiteProjectSampleViewModel(
                key=str(project.get("key") or ""),
                name=str(project.get("name") or ""),
                project_type_key=_as_str(project.get("project_type_key")),
                style=_as_str(project.get("style")),
                simplified=project.get("simplified"),
                is_private=project.get("is_private"),
            )
        )
    return projects


def _extract_category_counts(site: Dict[str, Any]) -> Dict[str, int]:
    counts = _deep_first(site, ["audit_summary.category_counts"])
    if not isinstance(counts, dict):
        return {}

    output: Dict[str, int] = {}
    for key, value in counts.items():
        parsed = _safe_int(value)
        output[str(key)] = parsed if parsed is not None else 0
    return output


def _extract_audit_records_sample(site: Dict[str, Any]) -> List[AuditRecordSampleViewModel]:
    records = _deep_first(site, ["audit_summary.records_sample"])
    if not isinstance(records, list):
        return []

    output: List[AuditRecordSampleViewModel] = []
    for record in records[:8]:
        if not isinstance(record, dict):
            continue

        object_name = None
        object_item = record.get("objectItem")
        if isinstance(object_item, dict):
            object_name = object_item.get("name")

        output.append(
            AuditRecordSampleViewModel(
                audit_id=_as_str(record.get("id")),
                created=_format_timestamp_for_ui(_as_str(record.get("created"))),
                category=_as_str(record.get("category")),
                summary=_as_str(record.get("summary")),
                object_name=_as_str(object_name),
            )
        )

    return output


def _pick_latest_collected_at(
    cards: List[SiteCardViewModel],
    fallback: Optional[str],
) -> Optional[str]:
    raw_timestamps = [card.last_collected for card in cards if card.last_collected]

    if fallback:
        raw_timestamps.append(fallback)

    if not raw_timestamps:
        return fallback

    parsed = []
    for timestamp in raw_timestamps:
        dt = _parse_datetime(timestamp)
        if dt is not None:
            parsed.append((dt, timestamp))

    if not parsed:
        return _format_timestamp_for_ui(raw_timestamps[0])

    parsed.sort(key=lambda item: item[0], reverse=True)
    return _format_timestamp_for_ui(parsed[0][1])


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

    return dt


def _format_timestamp_for_ui(value: Optional[str]) -> Optional[str]:
    dt = _parse_datetime(value)
    if dt is None:
        return value
    return dt.strftime("%d %b %Y %H:%M UTC")


def _compute_usage_percent(
    licensed_users_estimate: Optional[int],
    seats: Optional[int],
) -> Optional[int]:
    if licensed_users_estimate is None or seats is None or seats <= 0:
        return None

    try:
        return max(0, min(100, round((licensed_users_estimate / seats) * 100)))
    except ZeroDivisionError:
        return None


def _is_active_operational_site(site: Dict[str, Any]) -> bool:
    site_url = _extract_site_url(site)
    if site_url in ACTIVE_SITE_URLS:
        return True

    combined = " ".join(
        str(part).lower()
        for part in [
            site.get("site_key"),
            site.get("site_name"),
            site.get("name"),
            site.get("site_url"),
            site.get("url"),
            site.get("base_url"),
        ]
        if part
    )

    if any(token in combined for token in EXCLUDED_SITE_TOKENS):
        return False

    return False


def _extract_site_url(site: Dict[str, Any]) -> str:
    value = _as_str(
        _deep_first(
            site,
            [
                "url",
                "site_url",
                "base_url",
                "server_info.base_url",
            ],
        )
    ) or ""
    return value.rstrip("/")


def _extract_site_name(site: Dict[str, Any], site_url: str) -> str:
    explicit_name = _as_str(
        _deep_first(
            site,
            [
                "name",
                "site_name",
                "site_key",
            ],
        )
    )
    if explicit_name:
        return explicit_name

    if site_url:
        cleaned = site_url.replace("https://", "").replace("http://", "")
        return cleaned.split(".")[0]

    return "unknown-site"


def _slugify_site_name(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _deep_first(data: Dict[str, Any], paths: List[str]) -> Any:
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


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _bool_to_status(value: Any) -> Optional[str]:
    if value is True:
        return "available"
    if value is False:
        return "permission_limited"
    return None
