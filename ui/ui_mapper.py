import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ui.view_models import (
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
    latest_run_path = root / "latest_run.json"

    if not latest_run_path.exists():
        return {
            "collected_at": None,
            "sites": [],
        }

    try:
        with latest_run_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except Exception:
        return {
            "collected_at": None,
            "sites": [],
        }

    return normalize_backend_payload(raw)


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

    users = SiteUsersViewModel(
        total_users=_safe_int(_deep_first(site, ["user_summary.total_users"])),
        active_users=_safe_int(_deep_first(site, ["user_summary.active_users"])),
        inactive_users=_safe_int(_deep_first(site, ["user_summary.inactive_users"])),
    )

    licensed_users_estimate = _safe_int(
        _deep_first(site, ["licence_summary.licensed_users_estimate"])
    )
    seats = _safe_int(
        _deep_first(
            site,
            [
                "licence_summary.products.0.number_of_seats",
                "application_role_sample.0.number_of_seats",
            ],
        )
    )
    remaining_seats = _safe_int(
        _deep_first(
            site,
            [
                "licence_summary.products.0.remaining_seats",
                "application_role_sample.0.remaining_seats",
            ],
        )
    )

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
    )

    permissions = _extract_permissions_view_model(site)

    collected_at = (
        _as_str(
            _deep_first(
                site,
                [
                    "collected_at_utc",
                    "run_timestamp_local",
                    "collected_at",
                    "snapshot_collected_at",
                    "last_collected",
                    "run_timestamp_utc",
                ],
            )
        )
        or fallback_collected_at
    )

    growth_status = _as_str(_deep_first(site, ["growth_status"]))
    delta_available = any(
        _deep_first(site, [field]) is not None
        for field in [
            "project_count_delta",
            "total_users_delta",
            "active_users_delta",
            "inactive_users_delta",
            "licensed_users_estimate_delta",
            "issue_count_total_delta",
            "issue_count_unresolved_delta",
        ]
    )

    snapshot = SiteSnapshotViewModel(
        collected_at=collected_at,
        growth_status=growth_status,
        delta_available=delta_available,
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
        last_collected=collected_at,
    )


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


def _pick_latest_collected_at(
    cards: List[SiteCardViewModel],
    fallback: Optional[str],
) -> Optional[str]:
    timestamps = [card.last_collected for card in cards if card.last_collected]
    if not timestamps:
        return fallback

    parsed = []
    for timestamp in timestamps:
        dt = _parse_datetime(timestamp)
        if dt is not None:
            parsed.append((dt, timestamp))

    if not parsed:
        return timestamps[0]

    parsed.sort(key=lambda item: item[0], reverse=True)
    return parsed[0][1]


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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