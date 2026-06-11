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


# Real billing truth from your notes
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
    """
    Loads latest_run.json from the project root.
    """
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
    """
    Best-effort normalization so the UI can tolerate small contract changes.
    """
    if not isinstance(raw, dict):
        return {"collected_at": None, "sites": []}

    collected_at = (
        raw.get("collected_at")
        or raw.get("snapshot_collected_at")
        or raw.get("generated_at")
    )

    sites = raw.get("sites")
    if isinstance(sites, list):
        return {
            "collected_at": collected_at,
            "sites": [site for site in sites if isinstance(site, dict)],
        }

    if isinstance(raw.get("site_results"), list):
        return {
            "collected_at": collected_at,
            "sites": [site for site in raw.get("site_results", []) if isinstance(site, dict)],
        }

    if isinstance(raw.get("data"), dict) and isinstance(raw["data"].get("sites"), list):
        return {
            "collected_at": collected_at,
            "sites": [site for site in raw["data"]["sites"] if isinstance(site, dict)],
        }

    possible_sites = []
    for _, value in raw.items():
        if isinstance(value, dict) and (
            value.get("site_url") or value.get("url") or value.get("base_url")
        ):
            possible_sites.append(value)

    return {
        "collected_at": collected_at,
        "sites": possible_sites,
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
        total_updated_last_7_days=sum(card.metrics.updated_last_7_days_count for card in cards),
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


def _build_site_card(site: Dict[str, Any], fallback_collected_at: Optional[str]) -> SiteCardViewModel:
    site_url = _extract_site_url(site)
    site_name = _extract_site_name(site, site_url)
    site_key = _slugify_site_name(site_name)

    metrics = SiteMetricViewModel(
        project_count=_safe_int(_first(site, ["project_count", "projects_count"])) or 0,
        issue_count=_safe_int(_first(site, ["issue_count", "issues_count"])) or 0,
        unresolved_issue_count=_safe_int(_first(site, ["unresolved_issue_count"])) or 0,
        updated_last_7_days_count=_safe_int(_first(site, ["updated_last_7_days_count"])) or 0,
    )

    users = SiteUsersViewModel(
        total_users=_safe_int(_first(site, ["total_users"])),
        active_users=_safe_int(_first(site, ["active_users"])),
        inactive_users=_safe_int(_first(site, ["inactive_users"])),
    )

    licence = SiteLicenceViewModel(
        licensed_users_estimate=_safe_int(_first(site, ["licensed_users_estimate"])),
        seats=_safe_int(_first(site, ["seats"])),
        remaining_seats=_safe_int(_first(site, ["remaining_seats"])),
        licence_status=_as_str(_first(site, ["licence_status", "license_status"])),
        licence_api_access=_as_str(_first(site, ["licence_api_access", "license_api_access"])),
    )

    audit = SiteAuditViewModel(
        audit_status=_as_str(_first(site, ["audit_status"])),
        audit_api_access=_as_str(_first(site, ["audit_api_access"])),
    )

    permissions = _extract_permissions_view_model(site)

    collected_at = (
        _as_str(_first(site, ["collected_at", "snapshot_collected_at", "last_collected"]))
        or fallback_collected_at
    )
    growth_status = _as_str(_first(site, ["growth_status"]))
    delta_available = bool(_first(site, ["delta", "snapshot_delta", "delta_summary"]))

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
        usage_percent=usage_percent,
        last_collected=collected_at,
    )


def _extract_permissions_view_model(site: Dict[str, Any]) -> SitePermissionsViewModel:
    permissions = site.get("permissions") or site.get("permission_checker") or site.get("mypermissions")
    if not isinstance(permissions, dict):
        return SitePermissionsViewModel()

    overall_status = permissions.get("overall_status") or permissions.get("status")
    granted_count = 0
    denied_count = 0
    total_count = 0

    perms = permissions.get("permissions")
    if isinstance(perms, dict):
        for _, value in perms.items():
            granted = False

            if isinstance(value, dict):
                granted = bool(value.get("havePermission") or value.get("granted"))
            elif isinstance(value, bool):
                granted = value

            total_count += 1
            if granted:
                granted_count += 1
            else:
                denied_count += 1

        if not overall_status:
            if denied_count > 0:
                overall_status = "warning"
            elif granted_count > 0:
                overall_status = "ok"

    return SitePermissionsViewModel(
        overall_status=_as_str(overall_status),
        granted_count=granted_count,
        denied_count=denied_count,
        total_count=total_count,
    )


def _pick_latest_collected_at(cards: List[SiteCardViewModel], fallback: Optional[str]) -> Optional[str]:
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


def _compute_usage_percent(licensed_users_estimate: Optional[int], seats: Optional[int]) -> Optional[int]:
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
    value = _as_str(_first(site, ["site_url", "url", "base_url"])) or ""
    return value.rstrip("/")


def _extract_site_name(site: Dict[str, Any], site_url: str) -> str:
    explicit_name = _as_str(_first(site, ["site_name", "name", "site_key"]))
    if explicit_name:
        return explicit_name

    if site_url:
        cleaned = site_url.replace("https://", "").replace("http://", "")
        return cleaned.split(".")[0]

    return "unknown-site"


def _slugify_site_name(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _first(data: Dict[str, Any], keys: List[str]) -> Any:
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


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)